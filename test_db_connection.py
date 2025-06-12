import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

def test_connection():
    """
    Tests the database connection using credentials from the .env file.
    """
    print("--- Starting Database Connection Test ---")
    
    # Load environment variables from .env file
    load_dotenv(dotenv_path=".env")
    db_url = os.getenv("SYNC_SQLALCHEMY_DATABASE_URL")
    print(db_url)
    
    if not db_url:
        print("\n[ERROR] SYNC_SQLALCHEMY_DATABASE_URL not found in .env file.")
        print("Please make sure your .env file is in the root directory and contains the correct variable.")
        return

    print(f"Attempting to connect to the database...")
    # Masking password for security
    try:
        parts = db_url.split('@')
        user_pass = parts[0].split('//')[1]
        user = user_pass.split(':')[0]
        host_db = parts[1]
        print(f"Connecting with user '{user}' to host '{host_db}'")
    except Exception:
        print("Could not parse URL to display connection info, but proceeding anyway.")

    try:
        # Create a synchronous engine
        engine = create_engine(db_url)
        
        # Try to connect and execute a simple query
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            for row in result:
                if row[0] == 1:
                    print("\n[SUCCESS] Connection to the database was successful!")
                    print("Your credentials in the .env file are correct and the database is reachable.")
                else:
                    print("\n[ERROR] Connected, but query returned unexpected result.")
            
    except OperationalError as e:
        print("\n[ERROR] OperationalError: Could not connect to the database.")
        print("This is likely an issue with your credentials, hostname, or network access.")
        print("Please double-check:")
        print("  1. The USERNAME, PASSWORD, and HOSTNAME in your SYNC_SQLALCHEMY_DATABASE_URL.")
        print("  2. That your AlwaysData database accepts remote connections (it should by default).")
        print(f"\n--- SQLAlchemy Error Details ---\n{e}\n--------------------------------")

    except ProgrammingError as e:
        print(f"\n[ERROR] ProgrammingError: This often means you connected to the wrong database schema.")
        print(f"\n--- SQLAlchemy Error Details ---\n{e}\n--------------------------------")

    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {type(e).__name__}")
        print(f"\n--- Error Details ---\n{e}\n---------------------")

if __name__ == "__main__":
    test_connection() 