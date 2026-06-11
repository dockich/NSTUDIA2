import sqlite3

def clear_database():
    conn = sqlite3.connect("barbershop.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients")
    conn.commit()
    conn.close()
    print("✅ Все записи успешно удалены!")

if __name__ == "__main__":
    confirm = input("Вы уверены что хотите удалить ВСЕ записи? (да/нет): ")
    if confirm.lower() == "да":
        clear_database()
    else:
        print("Операция отменена.")