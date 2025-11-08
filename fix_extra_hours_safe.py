"""
Safe script to add extra_hours column with proper error handling.
This will work even if the column already exists.
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Use IF NOT EXISTS equivalent for PostgreSQL
        # First, check if column exists
        result = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'attendances' 
            AND column_name = 'extra_hours'
            AND table_schema = 'public'
        """))
        
        exists = result.scalar() > 0
        
        if exists:
            print("[INFO] Column 'extra_hours' already exists. Skipping creation.")
        else:
            print("[INFO] Adding 'extra_hours' column to attendances table...")
            
            # Add the column
            db.session.execute(text("""
                ALTER TABLE attendances 
                ADD COLUMN IF NOT EXISTS extra_hours DOUBLE PRECISION DEFAULT 0.0
            """))
            
            db.session.commit()
            print("[SUCCESS] Column 'extra_hours' added successfully.")
        
        # Update existing records to calculate extra_hours (safe to run multiple times)
        print("[INFO] Updating existing records with extra_hours values...")
        result = db.session.execute(text("""
            UPDATE attendances 
            SET extra_hours = GREATEST(0.0, COALESCE(working_hours, 0) - 8.0)
            WHERE working_hours IS NOT NULL 
            AND working_hours > 0
            AND (extra_hours IS NULL OR extra_hours = 0)
        """))
        
        updated_count = result.rowcount
        db.session.commit()
        
        if updated_count > 0:
            print(f"[SUCCESS] Updated {updated_count} existing records with extra_hours values.")
        else:
            print("[INFO] No records needed updating.")
            
        print("\n[SUCCESS] Database migration completed successfully!")
        print("Please restart your Flask application to ensure the changes take effect.")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
        print("\n[TIP] If the column already exists, the error can be ignored.")
        print("      Try restarting your Flask application.")
    finally:
        db.session.close()

