#!/usr/bin/env python3
"""
Migration script to move Profile.mde data into Profile.data["edr_mde"]
Run this before removing the mde column from the database model.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from detonatorapi.database import Profile

def migrate_mde_to_data():
    """Migrate all Profile.mde data to Profile.data["edr_mde"]"""
    
    # Connect to database
    SQLALCHEMY_DATABASE_URL = "sqlite:///./detonator.db"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        profiles = db.query(Profile).all()
        migrated_count = 0
        
        for profile in profiles:
            # Check if profile has mde data
            if profile.mde:
                print(f"Migrating profile '{profile.name}' (ID: {profile.id})")
                print(f"  Current mde data: {profile.mde}")
                
                # Move mde data to data["edr_mde"]
                if profile.data is None:
                    profile.data = {}
                
                profile.data["edr_mde"] = profile.mde
                
                # Clear the old mde field
                profile.mde = {}
                
                migrated_count += 1
                print(f"  Migrated to data['edr_mde']")
            else:
                # Ensure edr_mde exists even if empty
                if profile.data is None:
                    profile.data = {}
                if "edr_mde" not in profile.data:
                    profile.data["edr_mde"] = {}
        
        db.commit()
        print(f"\n✅ Migration complete: {migrated_count} profiles migrated")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting migration: Profile.mde -> Profile.data['edr_mde']")
    print("=" * 60)
    migrate_mde_to_data()
    print("=" * 60)
    print("Migration script completed successfully!")
    print("\nNext steps:")
    print("1. Verify the migration worked correctly")
    print("2. Update code to use profile.data.get('edr_mde', {}) instead of profile.mde")
    print("3. Remove the mde column from the database model")
