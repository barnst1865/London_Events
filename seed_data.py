#!/usr/bin/env python
"""Seed database with initial data."""
from app.database import SessionLocal, init_db
from app.models.database import Category
from slugify import slugify


CATEGORIES = [
    ("Music", "Live music, concerts, gigs, and performances", "🎵"),
    ("Theatre", "Plays, musicals, and theatrical performances", "🎭"),
    ("Comedy", "Stand-up comedy, improv, and comedy shows", "😂"),
    ("Sports", "Sporting events and competitions", "⚽"),
    ("Arts", "Art exhibitions, galleries, and visual arts", "🎨"),
    ("Film", "Cinema screenings and film festivals", "🎬"),
    ("Food", "Food festivals, tastings, and culinary events", "🍽️"),
    ("Family", "Family-friendly events and activities", "👨‍👩‍👧‍👦"),
    ("Festival", "Festivals and large-scale celebrations", "🎪"),
    ("Nightlife", "Clubs, parties, and nightlife events", "🌃"),
    ("Business", "Networking, conferences, and professional events", "💼"),
    ("Tech", "Technology conferences and meetups", "💻"),
    ("Wellness", "Health, fitness, and wellness events", "🧘"),
    ("Education", "Workshops, classes, and learning events", "📚"),
    ("Community", "Community events and gatherings", "🤝"),
    ("Other", "Other events and activities", "📍"),
]


def seed_categories():
    """Seed event categories into database."""
    db = SessionLocal()
    try:
        print("Initializing database...")
        init_db()

        print("Seeding categories...")
        for name, description, icon in CATEGORIES:
            # Check if exists
            existing = db.query(Category).filter(Category.name == name).first()
            if existing:
                print(f"  ✓ {name} (already exists)")
                continue

            category = Category(
                name=name,
                slug=slugify(name),
                description=description,
                icon=icon
            )
            db.add(category)
            print(f"  + {name}")

        db.commit()
        print("\n✓ Database seeded successfully!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_categories()
