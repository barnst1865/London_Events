"""Subscriptions API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models.database import User, Subscription, SubscriptionTier
from ..models import schemas
from ..api.auth import get_current_active_user
from ..config import settings

router = APIRouter()


@router.get("/plans")
async def get_subscription_plans():
    """Get available subscription plans."""
    return {
        "plans": [
            {
                "tier": "free",
                "name": "Free Sampler",
                "price": 0,
                "currency": "GBP",
                "interval": "month",
                "features": [
                    f"Preview of {settings.free_events_limit} upcoming events",
                    "Monthly newsletter",
                    "Basic event information"
                ]
            },
            {
                "tier": "monthly",
                "name": "Full Access - Monthly",
                "price": 4.99,
                "currency": "GBP",
                "interval": "month",
                "stripe_price_id": settings.monthly_price_id,
                "features": [
                    "All upcoming events",
                    "Advanced filtering",
                    "Ticket availability alerts",
                    "Selling out notifications",
                    "Personalized recommendations",
                    "Early access to special events"
                ]
            },
            {
                "tier": "annual",
                "name": "Full Access - Annual",
                "price": 49.99,
                "currency": "GBP",
                "interval": "year",
                "stripe_price_id": settings.annual_price_id,
                "features": [
                    "All monthly features",
                    "2 months free (save 17%)",
                    "Priority support"
                ]
            }
        ]
    }


@router.get("/my-subscription", response_model=schemas.Subscription)
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription."""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return subscription


@router.post("/checkout-session")
async def create_checkout_session(
    tier: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe checkout session for subscription.

    Args:
        tier: Subscription tier (monthly or annual)

    Returns:
        Stripe checkout session URL
    """
    if not settings.stripe_api_key:
        raise HTTPException(
            status_code=503,
            detail="Payment processing not configured"
        )

    # Validate tier
    if tier not in ["monthly", "annual"]:
        raise HTTPException(status_code=400, detail="Invalid tier")

    # Get price ID
    price_id = settings.monthly_price_id if tier == "monthly" else settings.annual_price_id

    if not price_id:
        raise HTTPException(
            status_code=503,
            detail="Subscription plan not configured"
        )

    # Create Stripe checkout session
    try:
        import stripe
        stripe.api_key = settings.stripe_api_key

        # Get or create Stripe customer
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id
        ).first()

        customer_id = subscription.stripe_customer_id if subscription else None

        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": current_user.id}
            )
            customer_id = customer.id

            # Update subscription with customer ID
            if subscription:
                subscription.stripe_customer_id = customer_id
                db.commit()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{settings.app_name}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.app_name}/subscription/cancel",
            metadata={
                "user_id": current_user.id,
                "tier": tier
            }
        )

        return {"checkout_url": session.url}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    Updates subscription status based on Stripe events.
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhooks not configured")

    import stripe
    stripe.api_key = settings.stripe_api_key

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle different event types
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        tier = session["metadata"]["tier"]

        # Update subscription
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).first()

        if subscription:
            subscription.tier = SubscriptionTier[tier.upper()]
            subscription.stripe_subscription_id = session["subscription"]
            subscription.status = "active"
            db.commit()

    elif event["type"] == "customer.subscription.updated":
        stripe_sub = event["data"]["object"]
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub["id"]
        ).first()

        if subscription:
            subscription.status = stripe_sub["status"]
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_sub["current_period_start"]
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_sub["current_period_end"]
            )
            subscription.cancel_at_period_end = stripe_sub["cancel_at_period_end"]
            db.commit()

    elif event["type"] == "customer.subscription.deleted":
        stripe_sub = event["data"]["object"]
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub["id"]
        ).first()

        if subscription:
            subscription.tier = SubscriptionTier.FREE
            subscription.status = "cancelled"
            db.commit()

    return {"status": "success"}


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel current subscription (at end of period)."""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription")

    try:
        import stripe
        stripe.api_key = settings.stripe_api_key

        # Cancel at period end
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )

        subscription.cancel_at_period_end = True
        db.commit()

        return {"status": "success", "message": "Subscription will cancel at period end"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel subscription: {str(e)}"
        )
