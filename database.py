import sqlite3
import json
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "rifa.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabela de configurações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Tabela de pedidos / reservas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_name TEXT NOT NULL,
        buyer_phone TEXT NOT NULL,
        buyer_email TEXT,
        seller_name TEXT NOT NULL,
        seller_phone TEXT,
        total_tickets INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pendente',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        confirmed_at TIMESTAMP,
        confirmed_by TEXT
    )
    """)

    # Tabela de números da rifa (1 a 2000)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        number INTEGER PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'disponivel',
        order_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL
    )
    """)

    # Configurações padrão
    default_configs = {
        "title": "Grande Rifa Beneficente",
        "subtitle": "Em prol do Retiro Espiritual 2027",
        "church_name": "Nossa Igreja",
        "retreat_year": "2027",
        "price_per_ticket": "10.00",
        "total_tickets": "2000",
        "pix_key": "retiro2027@igreja.org",
        "pix_type": "Chave Aleatória / E-mail",
        "pix_beneficiary": "Tesouraria / Coordenação do Retiro",
        "pix_bank": "Banco Inter / Nubank",
        "leader_whatsapp": "5511999999999",
        "admin_password": "lideres2027",
        "draw_date": "19 de Dezembro de 2026",
        "draw_location": "Culto Especial de Jovens & Família",
        "prizes": json.dumps([
            {"place": "1º Prêmio", "title": "PIX de R$ 1.000,00", "desc": "Transferência de R$ 1.000,00 direto na sua conta via Pix"},
            {"place": "2º Prêmio", "title": "PIX de R$ 500,00", "desc": "Transferência de R$ 500,00 direto na sua conta via Pix"}
        ]),
        "intro_text": "Nosso Retiro Espiritual 2027 será um momento inesquecível de comunhão, adoração e transformação de vidas! Toda a renda desta rifa será 100% revertida para subsidiar o transporte, alimentação e estadia dos nossos jovens e participantes. Ao comprar um ponto, você investe diretamente no Reino de Deus!",
        "bible_verse": "Cada um dê conforme determinou em seu coração, não com tristeza ou por obrigação, pois Deus ama quem dá com alegria. (2 Coríntios 9:7)"
    }

    for key, val in default_configs.items():
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, val))

    # Verificar se os 2000 números foram gerados
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    if count == 0:
        tickets_data = [(i, 'disponivel', None) for i in range(1, 2001)]
        cursor.executemany("INSERT INTO tickets (number, status, order_id) VALUES (?, ?, ?)", tickets_data)

    conn.commit()
    conn.close()

def get_config():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM config")
    rows = cursor.fetchall()
    conn.close()
    config_dict = {row["key"]: row["value"] for row in rows}
    if "prizes" in config_dict:
        try:
            config_dict["prizes_list"] = json.loads(config_dict["prizes"])
        except:
            config_dict["prizes_list"] = []
    return config_dict

def update_config(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        COUNT(CASE WHEN status = 'pago' THEN 1 END) as paid_count,
        COUNT(CASE WHEN status = 'reservado' THEN 1 END) as reserved_count,
        COUNT(CASE WHEN status = 'disponivel' THEN 1 END) as available_count,
        COUNT(*) as total_count
    FROM tickets
    """)
    row = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(DISTINCT seller_name) FROM orders WHERE status != 'cancelado'")
    seller_count = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = 'confirmado'")
    total_paid_amount = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = 'pendente'")
    total_pending_amount = cursor.fetchone()[0]

    conn.close()
    return {
        "paid_count": row["paid_count"],
        "reserved_count": row["reserved_count"],
        "available_count": row["available_count"],
        "total_count": row["total_count"],
        "seller_count": seller_count,
        "total_paid_amount": round(total_paid_amount, 2),
        "total_pending_amount": round(total_pending_amount, 2),
        "percentage_paid": round((row["paid_count"] / row["total_count"]) * 100, 1) if row["total_count"] else 0
    }

def get_tickets(page=1, page_size=200, status_filter=None, search_number=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT t.number, t.status, t.order_id, o.buyer_name, o.seller_name
    FROM tickets t
    LEFT JOIN orders o ON t.order_id = o.id
    WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND t.status = ?"
        params.append(status_filter)

    if search_number:
        query += " AND t.number = ?"
        params.append(search_number)

    query += " ORDER BY t.number ASC"

    if page is not None and page_size is not None:
        offset = (page - 1) * page_size
        query += " LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def get_available_numbers(limit=2000):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT number FROM tickets WHERE status = 'disponivel' ORDER BY number ASC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [row["number"] for row in rows]

def create_order(buyer_name, buyer_phone, seller_name, numbers, buyer_email="", seller_phone="", notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Validar números
        if not numbers:
            raise ValueError("Nenhum número selecionado.")

        # Verificar se algum número já está ocupado
        placeholders = ",".join("?" for _ in numbers)
        cursor.execute(f"SELECT number, status FROM tickets WHERE number IN ({placeholders})", numbers)
        existing = cursor.fetchall()

        if len(existing) != len(numbers):
            raise ValueError("Alguns números informados são inválidos (fora do intervalo 1 a 2000).")

        unavailable = [row["number"] for row in existing if row["status"] != 'disponivel']
        if unavailable:
            raise ValueError(f"Os seguintes números já foram reservados ou pagos: {', '.join(str(n).zfill(4) for n in unavailable)}")

        # Obter preço por bilhete
        cursor.execute("SELECT value FROM config WHERE key = 'price_per_ticket'")
        price_row = cursor.fetchone()
        price_per_ticket = float(price_row["value"]) if price_row else 10.0

        total_amount = len(numbers) * price_per_ticket

        # Inserir pedido
        cursor.execute("""
        INSERT INTO orders (buyer_name, buyer_phone, buyer_email, seller_name, seller_phone, total_tickets, total_amount, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?)
        """, (buyer_name.strip(), buyer_phone.strip(), buyer_email.strip(), seller_name.strip(), seller_phone.strip(), len(numbers), total_amount, notes.strip()))
        order_id = cursor.lastrowid

        # Atualizar tickets
        cursor.execute(f"""
        UPDATE tickets
        SET status = 'reservado', order_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE number IN ({placeholders})
        """, [order_id] + numbers)

        conn.commit()
        return {
            "order_id": order_id,
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "seller_name": seller_name,
            "numbers": sorted(numbers),
            "total_tickets": len(numbers),
            "total_amount": total_amount,
            "status": "pendente"
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def confirm_order(order_id, confirmed_by="Líder"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise ValueError("Pedido não encontrado.")

        cursor.execute("""
        UPDATE orders
        SET status = 'confirmado', confirmed_at = CURRENT_TIMESTAMP, confirmed_by = ?
        WHERE id = ?
        """, (confirmed_by, order_id))

        cursor.execute("""
        UPDATE tickets
        SET status = 'pago', updated_at = CURRENT_TIMESTAMP
        WHERE order_id = ?
        """, (order_id,))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def cancel_order(order_id, reason="Cancelado pelo líder"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise ValueError("Pedido não encontrado.")

        cursor.execute("""
        UPDATE orders
        SET status = 'cancelado', notes = coalesce(notes, '') || ' [Cancelamento: ' || ? || ']'
        WHERE id = ?
        """, (reason, order_id))

        cursor.execute("""
        UPDATE tickets
        SET status = 'disponivel', order_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE order_id = ?
        """, (order_id,))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_orders(status_filter=None, seller_filter=None, search=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT o.*, GROUP_CONCAT(t.number, ', ') as ticket_numbers
    FROM orders o
    LEFT JOIN tickets t ON t.order_id = o.id
    WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND o.status = ?"
        params.append(status_filter)

    if seller_filter:
        query += " AND o.seller_name LIKE ?"
        params.append(f"%{seller_filter}%")

    if search:
        query += " AND (o.buyer_name LIKE ? OR o.buyer_phone LIKE ? OR o.id = ?)"
        params.extend([f"%{search}%", f"%{search}%", search if search.isdigit() else -1])

    query += " GROUP BY o.id ORDER BY o.created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        item = dict(row)
        num_str = item.get("ticket_numbers") or ""
        item["ticket_list"] = [int(n.strip()) for n in num_str.split(",") if n.strip().isdigit()]
        results.append(item)
    return results

def search_buyer_tickets(query_term):
    conn = get_connection()
    cursor = conn.cursor()
    
    clean_term = query_term.strip()
    # Busca por telefone ou nome
    cursor.execute("""
    SELECT o.id, o.buyer_name, o.buyer_phone, o.seller_name, o.status, o.total_amount, o.created_at, o.confirmed_at,
           GROUP_CONCAT(t.number, ', ') as ticket_numbers
    FROM orders o
    JOIN tickets t ON t.order_id = o.id
    WHERE (o.buyer_name LIKE ? OR o.buyer_phone LIKE ?) AND o.status != 'cancelado'
    GROUP BY o.id
    ORDER BY o.created_at DESC
    """, (f"%{clean_term}%", f"%{clean_term}%"))
    
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        raw_nums = d.get("ticket_numbers") or ""
        d["ticket_list"] = [int(x.strip()) for x in raw_nums.split(",") if x.strip().isdigit()]
        results.append(d)
    return results

def get_seller_ranking():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        seller_name,
        COUNT(CASE WHEN status = 'confirmado' THEN 1 END) as paid_orders,
        COALESCE(SUM(CASE WHEN status = 'confirmado' THEN total_tickets ELSE 0 END), 0) as paid_tickets,
        COALESCE(SUM(CASE WHEN status = 'confirmado' THEN total_amount ELSE 0 END), 0) as paid_amount,
        COUNT(CASE WHEN status = 'pendente' THEN 1 END) as pending_orders,
        COALESCE(SUM(CASE WHEN status = 'pendente' THEN total_tickets ELSE 0 END), 0) as pending_tickets
    FROM orders
    WHERE status != 'cancelado' AND seller_name IS NOT NULL AND seller_name != ''
    GROUP BY seller_name
    ORDER BY paid_tickets DESC, pending_tickets DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_confirmed_tickets_for_draw():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.number, o.buyer_name, o.buyer_phone, o.seller_name, o.confirmed_at
    FROM tickets t
    JOIN orders o ON t.order_id = o.id
    WHERE t.status = 'pago' AND o.status = 'confirmado'
    ORDER BY t.number ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
