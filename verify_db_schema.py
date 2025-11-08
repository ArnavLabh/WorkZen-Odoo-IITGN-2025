"""
Script to verify the database schema and add extra_hours column if needed.
This script will check the actual database state and fix it.
"""
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    try:
        # Get the database engine
        engine = db.engine
        
        # Check if attendances table exists and get its columns
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'attendances' not in tables:
            print("[ERROR] Table 'attendances' does not exist in the database.")
            print("Please run 'python create_tables.py' first to create the tables.")
            exit(1)
        
        # Get columns from attendances table
        columns = [col['name'] for col in inspector.get_columns('attendances')]
        print(f"[INFO] Current columns in attendances table: {', '.join(columns)}")
        
        if 'extra_hours' in columns:
            print("[SUCCESS] Column 'extra_hours' already exists in attendances table.")
        else:
            print("[INFO] Column 'extra_hours' does not exist. Adding it now...")
            
            # Add the extra_hours column
            db.session.execute(text("""
                ALTER TABLE attendances 
                ADD COLUMN extra_hours DOUBLE PRECISION DEFAULT 0.0
            """))
            
            # Update existing records to calculate extra_hours
            db.session.execute(text("""
                UPDATE attendances 
                SET extra_hours = GREATEST(0.0, COALESCE(working_hours, 0) - 8.0)
                WHERE working_hours IS NOT NULL AND working_hours > 0
            """))
            
            db.session.commit()
            print("[SUCCESS] Successfully added 'extra_hours' column to attendances table.")
            print("[SUCCESS] Updated existing records with calculated extra_hours values.")
            
            # Verify the column was added
            columns_after = [col['name'] for col in inspector.get_columns('attendances')]
            if 'extra_hours' in columns_after:
                print("[SUCCESS] Verification: Column 'extra_hours' is now in the table.")
            else:
                print("[ERROR] Verification failed: Column was not added.")
                
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nAlternative: If you're using Flask-Migrate, run:")
        print("  flask db migrate -m 'Add extra_hours to Attendance model'")
        print("  flask db upgrade")
    finally:
        db.session.close()

