from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import io
import csv
import database

app = FastAPI(title="Sistema Pix Premiado - Retiro 2027", version="1.0.0")

# Inicializa banco de dados ao carregar
database.init_db()

# Modelos Pydantic
class OrderCreateRequest(BaseModel):
    buyer_name: str = Field(..., min_length=2)
    buyer_phone: str = Field(..., min_length=8)
    seller_name: str = Field(..., min_length=2)
    numbers: List[int]
    buyer_email: Optional[str] = ""
    seller_phone: Optional[str] = ""
    notes: Optional[str] = ""

class LoginRequest(BaseModel):
    password: str

class ConfigUpdateRequest(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    church_name: Optional[str] = None
    price_per_ticket: Optional[str] = None
    pix_key: Optional[str] = None
    pix_type: Optional[str] = None
    pix_beneficiary: Optional[str] = None
    pix_bank: Optional[str] = None
    pix_payload: Optional[str] = None
    leader_whatsapp: Optional[str] = None
    admin_password: Optional[str] = None
    draw_date: Optional[str] = None
    draw_location: Optional[str] = None
    prizes: Optional[str] = None
    intro_text: Optional[str] = None
    bible_verse: Optional[str] = None

# Middleware / Dependency de autenticação de líderes
def verify_admin(authorization: Optional[str] = Header(None)):
    config = database.get_config()
    real_password = config.get("admin_password", "lideres2027")
    if not authorization:
        raise HTTPException(status_code=401, detail="Senha de líderes não informada.")
    
    # Suporta "Bearer <token>" ou envio direto da senha
    token = authorization.replace("Bearer ", "").strip()
    if token != real_password:
        raise HTTPException(status_code=403, detail="Senha de acesso inválida.")
    return True

# --- ROTAS PÚBLICAS ---

@app.get("/api/config")
def get_public_config():
    conf = database.get_config()
    # Não expor a senha pública
    conf_safe = {k: v for k, v in conf.items() if k != "admin_password"}
    return conf_safe

@app.get("/api/stats")
def get_public_stats():
    return database.get_stats()

@app.get("/api/tickets")
def get_tickets_list(
    page: Optional[int] = Query(None),
    page_size: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[int] = Query(None)
):
    tickets = database.get_tickets(page=page, page_size=page_size, status_filter=status, search_number=search)
    return tickets

@app.get("/api/available-numbers")
def get_available_numbers(limit: int = 2000):
    return database.get_available_numbers(limit=limit)

@app.post("/api/orders")
def create_new_order(order_data: OrderCreateRequest):
    try:
        result = database.create_order(
            buyer_name=order_data.buyer_name,
            buyer_phone=order_data.buyer_phone,
            seller_name=order_data.seller_name,
            numbers=order_data.numbers,
            buyer_email=order_data.buyer_email or "",
            seller_phone=order_data.seller_phone or "",
            notes=order_data.notes or ""
        )
        return {"success": True, "order": result}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao registrar pedido: {str(e)}")

@app.get("/api/buyer/search")
def search_buyer(q: str = Query(..., min_length=2)):
    results = database.search_buyer_tickets(q)
    return results

# --- ROTAS DE LÍDERES / ADMIN ---

@app.post("/api/admin/login")
def admin_login(req: LoginRequest):
    config = database.get_config()
    real_password = config.get("admin_password", "lideres2027")
    if req.password.strip() == real_password:
        return {"success": True, "token": req.password.strip()}
    raise HTTPException(status_code=401, detail="Senha incorreta.")

@app.get("/api/admin/orders")
def get_all_orders(
    status: Optional[str] = None,
    seller: Optional[str] = None,
    search: Optional[str] = None,
    auth: bool = Depends(verify_admin)
):
    return database.get_orders(status_filter=status, seller_filter=seller, search=search)

@app.post("/api/admin/orders/{order_id}/confirm")
def confirm_order_payment(order_id: int, request: Request, auth: bool = Depends(verify_admin)):
    try:
        # Tenta obter nome do líder se enviado
        body = {}
        try:
            body = getattr(request, "_json", {})
        except:
            pass
        leader_name = body.get("leader_name", "Líder") if isinstance(body, dict) else "Líder"
        
        database.confirm_order(order_id, confirmed_by=leader_name)
        return {"success": True, "message": "Pagamento confirmado com sucesso e números validados!"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/orders/{order_id}/cancel")
def cancel_order_reservation(order_id: int, request: Request, auth: bool = Depends(verify_admin)):
    try:
        database.cancel_order(order_id, reason="Cancelado pelo líder")
        return {"success": True, "message": "Reserva cancelada e números liberados!"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/ranking")
def get_seller_ranking_report(auth: bool = Depends(verify_admin)):
    return database.get_seller_ranking()

@app.get("/api/admin/draw-candidates")
def get_draw_candidates(auth: bool = Depends(verify_admin)):
    return database.get_confirmed_tickets_for_draw()

@app.post("/api/admin/config")
def update_system_config(conf: ConfigUpdateRequest, auth: bool = Depends(verify_admin)):
    updates = conf.model_dump(exclude_unset=True)
    for k, v in updates.items():
        if v is not None:
            database.update_config(k, v)
    return {"success": True, "message": "Configurações atualizadas com sucesso!"}

@app.get("/api/admin/export.csv")
def export_tickets_csv(token: Optional[str] = None):
    # Permite autenticação por query param no download
    config = database.get_config()
    real_password = config.get("admin_password", "lideres2027")
    if token != real_password:
        raise HTTPException(status_code=403, detail="Não autorizado.")

    tickets = database.get_tickets(page=None, page_size=None)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Numero", "Status", "ID_Pedido", "Nome_Comprador", "Nome_Vendedor"])
    
    for t in tickets:
        writer.writerow([
            str(t["number"]).zfill(4),
            t["status"],
            t["order_id"] or "",
            t["buyer_name"] or "",
            t["seller_name"] or ""
        ])

    output.seek(0)
    return Response(
        content=output.getvalue().encode('utf-8-sig'),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=relatorio_pix_premiado_retiro_2027.csv"}
    )

# --- SERVIR ARQUIVOS ESTÁTICOS / FRONTEND ---
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(os.path.join(STATIC_DIR, "index.html")) and os.path.exists(os.path.join(os.path.dirname(__file__), "index.html")):
    STATIC_DIR = os.path.dirname(__file__)

os.makedirs(STATIC_DIR, exist_ok=True)

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/vendedor")
def serve_vendedor():
    return FileResponse(os.path.join(STATIC_DIR, "vendedor.html"))

@app.get("/lideres")
def serve_lideres():
    return FileResponse(os.path.join(STATIC_DIR, "lideres.html"))

@app.get("/sorteio")
def serve_sorteio():
    return FileResponse(os.path.join(STATIC_DIR, "sorteio.html"))

@app.get("/qrcode_pix.jpg")
def serve_qr():
    p = os.path.join(STATIC_DIR, "qrcode_pix.jpg")
    if not os.path.exists(p):
        p = os.path.join(os.path.dirname(__file__), "qrcode_pix.jpg")
    return FileResponse(p)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
