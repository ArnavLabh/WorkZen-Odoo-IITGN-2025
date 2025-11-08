"""
Script to add extra_hours column to attendances table.
Run this script to update your existing database schema.
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Check if column already exists
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='attendances' AND column_name='extra_hours'
        """))
        
        if result.fetchone():
            print("[SUCCESS] Column 'extra_hours' already exists in attendances table.")
        else:
            # Add the extra_hours column
            db.session.execute(text("""
                ALTER TABLE attendances 
                ADD COLUMN extra_hours DOUBLE PRECISION DEFAULT 0.0
            """))
            
            # Update existing records to calculate extra_hours
            # This will set extra_hours to 0 for now, but they'll be recalculated on next checkout
            db.session.execute(text("""
                UPDATE attendances 
                SET extra_hours = GREATEST(0.0, working_hours - 8.0)
                WHERE working_hours IS NOT NULL AND working_hours > 0
            """))
            
            db.session.commit()
            print("[SUCCESS] Successfully added 'extra_hours' column to attendances table.")
            print("[SUCCESS] Updated existing records with calculated extra_hours values.")
            
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Error: {e}")
        print("\nIf you're using Flask-Migrate, you can also run:")
        print("  flask db migrate -m 'Add extra_hours to Attendance model'")
        print("  flask db upgrade")
    finally:
        db.session.close()

