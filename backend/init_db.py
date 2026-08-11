import os
from sqlalchemy import text
from models.database import engine

def init_db():
    sql_path = os.path.join(os.path.dirname(__file__), "models", "migrations", "init.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()
    
    with engine.connect() as conn:
        for statement in sql.split(';'):
            stmt = statement.strip()
            if stmt:
                try:
                    conn.execute(text(stmt))
                    conn.commit()
                except Exception as e:
                    print(f"Skipping statement due to error: {e}")
                    conn.rollback()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
