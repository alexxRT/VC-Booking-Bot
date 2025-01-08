import sqlite3

class data_base:
    db_path : str
    db_name : str

    connection : sqlite3.Connection
    cursor : sqlite3.Cursor

    def __init__(self, db_path):
        self.db_path = db_path
        self.db_name = "users"

        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.connection.cursor()

        columns  = "username varchar(50), usrid int"
        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS users (id int auto_increment primary key, {columns})")
        self.connection.commit()

    def __del__(self):
        self.cursor.close()
        self.connection.close()

    # add new user to data base
    def add_new_user(self, username: str, user_id: int):
        self.cursor.execute(f"INSERT INTO {self.db_name} (username, usrid) VALUES (?, ?)", (username, user_id))
        self.connection.commit()

        return

    def update_record(self, update: str, where: str):
        self.cursor.execute(f"UPDATE {self.db_name} SET {update} WHERE {where}")
        self.connection.commit()

        return

    def select_user(self, where: str):
        self.cursor.execute(f"SELECT * FROM {self.db_name} WHERE {where}")
        user = self.cursor.fetchone()

        return user

    def select_users(self, where: str) -> list:
        self.cursor.execute(f"SELECT * FROM {self.db_name} WHERE {where}")
        users = self.cursor.fetchall()

        return users


