import streamlit as st
import os
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from groq import Groq  # <-- GANTI: dari anthropic ke groq

# ---------- Database Setup (SQLite) ----------
DATABASE_URL = "sqlite:///./agent.db"
os.makedirs(os.path.dirname("./agent.db") if os.path.dirname("./agent.db") else ".", exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autoflush=False, bind=engine)
Base = declarative_base()

# ---------- Database Models ----------
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True)
    customer_id = Column(String(50))
    customer_name = Column(String(100))
    customer_email = Column(String(100))
    status = Column(String(50))
    shipping_status = Column(String(50))
    tracking_number = Column(String(100), nullable=True)
    order_date = Column(DateTime, default=datetime.utcnow)
    total_amount = Column(Float)
    items = Column(Text, nullable=True)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(50), unique=True, index=True)
    name = Column(String(200))
    price = Column(Float)
    stock_quantity = Column(Integer)
    category = Column(String(100))

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), unique=True, index=True)
    customer_id = Column(String(50))
    order_id = Column(String(50), nullable=True)
    issue = Column(Text)
    status = Column(String(50))
    priority = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True)
    user_message = Column(Text)
    assistant_message = Column(Text)
    tools_called = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ---------- Seed Sample Data ----------
def seed_data():
    db = SessionLocal()
    
    if db.query(Order).count() == 0:
        sample_orders = [
            Order(order_id="ORD-12345", customer_id="CUST-001", customer_name="John Doe", 
                  customer_email="john@example.com", status="delayed", 
                  shipping_status="delayed_at_sorting_facility", tracking_number="TRK123456789",
                  total_amount=299.99),
            Order(order_id="ORD-12346", customer_id="CUST-001", customer_name="John Doe",
                  customer_email="john@example.com", status="shipped",
                  shipping_status="in_transit", tracking_number="TRK987654321",
                  total_amount=49.99),
            Order(order_id="ORD-12347", customer_id="CUST-002", customer_name="Jane Smith",
                  customer_email="jane@example.com", status="delivered",
                  shipping_status="delivered", tracking_number="TRK555555555",
                  total_amount=1599.99),
            Order(order_id="ORD-12348", customer_id="CUST-003", customer_name="Bob Wilson",
                  customer_email="bob@example.com", status="processing",
                  shipping_status="being_packed", tracking_number=None,
                  total_amount=89.99),
        ]
        db.add_all(sample_orders)
    
    if db.query(Product).count() == 0:
        sample_products = [
            Product(product_id="P001", name="Wireless Headphones", price=99.99, stock_quantity=45, category="Electronics"),
            Product(product_id="P002", name="Laptop Stand", price=200.00, stock_quantity=12, category="Accessories"),
            Product(product_id="P003", name="Phone Case", price=49.99, stock_quantity=78, category="Accessories"),
            Product(product_id="P004", name="Smartphone", price=1599.99, stock_quantity=23, category="Electronics"),
            Product(product_id="P005", name="USB-C Cable", price=15.99, stock_quantity=150, category="Accessories"),
        ]
        db.add_all(sample_products)
    
    db.commit()
    db.close()

# ---------- Tool Functions ----------
def get_order_status(order_id: str) -> dict:
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found"}
        return {
            "success": True,
            "order_id": order.order_id,
            "status": order.status,
            "shipping_status": order.shipping_status,
            "tracking_number": order.tracking_number,
            "customer_name": order.customer_name,
            "total_amount": order.total_amount
        }
    finally:
        db.close()

def check_inventory(product_id: str) -> dict:
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if not product:
            return {"success": False, "error": f"Product {product_id} not found"}
        return {
            "success": True,
            "product_id": product.product_id,
            "product_name": product.name,
            "stock_quantity": product.stock_quantity,
            "status": "in_stock" if product.stock_quantity > 0 else "out_of_stock",
            "price": product.price
        }
    finally:
        db.close()

def create_support_ticket(customer_id: str, issue: str, order_id: str = None) -> dict:
    db = SessionLocal()
    try:
        ticket_count = db.query(SupportTicket).count()
        ticket_id = f"TKT-{ticket_count + 10001}"
        priority = "high" if any(word in issue.lower() for word in ["urgent", "late", "delay", "complaint"]) else "medium"
        
        ticket = SupportTicket(
            ticket_id=ticket_id, customer_id=customer_id, order_id=order_id,
            issue=issue, status="open", priority=priority
        )
        db.add(ticket)
        db.commit()
        return {"success": True, "ticket_id": ticket_id, "priority": priority}
    finally:
        db.close()

def process_refund(order_id: str, customer_id: str, reason: str) -> dict:
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found"}
        if order.customer_id != customer_id:
            return {"success": False, "error": "Customer ID does not match order"}
        if order.status in ["delayed", "shipped"]:
            order.status = "refunded"
            db.commit()
            return {"success": True, "refund_amount": order.total_amount}
        return {"success": False, "error": f"Order not eligible. Status: {order.status}"}
    finally:
        db.close()

# ---------- Tool Definitions for Groq ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Get order status and shipping information",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Order ID like ORD-12345"}},
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Check product availability",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string", "description": "Product ID like P001"}},
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create support ticket for escalation",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "issue": {"type": "string"},
                    "order_id": {"type": "string", "description": "Optional order ID"}
                },
                "required": ["customer_id", "issue"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_refund",
            "description": "Process refund for eligible orders",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "customer_id": {"type": "string"},
                    "reason": {"type": "string"}
                },
                "required": ["order_id", "customer_id", "reason"]
            }
        }
    }
]

TOOL_FUNCTIONS = {
    "get_order_status": get_order_status,
    "check_inventory": check_inventory,
    "create_support_ticket": create_support_ticket,
    "process_refund": process_refund
}

# ---------- Agent Class with Groq ----------
class CustomerSupportAgent:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"  # Model Groq gratis
    
    def process_message(self, user_message: str, session_id: str, history: list) -> dict:
        system_prompt = """You are a customer support agent with tools.

Tools:
- get_order_status: Check order status
- check_inventory: Check product stock
- create_support_ticket: Escalate issues
- process_refund: Process refunds

Guidelines:
1. Call tools to get information before answering
2. Always verify customer_id for refunds
3. Create tickets for complaints/delays
4. Be helpful and professional"""
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        
        tools_called = []
        tool_results = []
        response_text = ""
        
        for _ in range(5):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0
            )
            
            response_text = response.choices[0].message.content or ""
            tool_calls = response.choices[0].message.tool_calls
            
            if not tool_calls:
                break
            
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)
                tools_called.append({"tool": tool_name, "input": tool_input})
                
                if tool_name in TOOL_FUNCTIONS:
                    result = TOOL_FUNCTIONS[tool_name](**tool_input)
                    tool_results.append({"tool": tool_name, "result": result})
                    result_json = json.dumps(result)
                else:
                    result_json = json.dumps({"error": "Unknown tool"})
                
                messages.append(response.choices[0].message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_json
                })
        
        return {"response": response_text, "tools_called": tools_called, "tool_results": tool_results}

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Autonomous Agent - Customer Support", page_icon="🤖", layout="wide")

# Initialize database
Base.metadata.create_all(bind=engine)
seed_data()

# Sidebar
with st.sidebar:
    st.title("🤖 Autonomous Agent")
    st.markdown("---")
    st.markdown("### 🛠️ Tools Available")
    st.markdown("""
    - 📦 **Get Order Status** - Check order shipping
    - 📊 **Check Inventory** - Product availability
    - 🎫 **Create Ticket** - Escalate issues
    - 💰 **Process Refund** - Refund orders
    """)
    st.markdown("---")
    st.markdown("### 📝 Sample Questions")
    
    samples = [
        "Check order ORD-12345 status",
        "My order ORD-12345 is late! I want a refund. My customer ID is CUST-001",
        "Is product P004 in stock?",
        "I want to speak to a manager about my late order. Customer ID: CUST-001",
        "Check inventory for product P005"
    ]
    
    for sample in samples:
        if st.button(sample, use_container_width=True):
            st.session_state.sample_query = sample
            st.rerun()
    
    st.markdown("---")
    if st.button("🔄 New Conversation"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

st.title("🤖 Autonomous Customer Support Agent")
st.markdown("This AI agent can **take actions** - not just answer questions!")

# Initialize session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Get API key from secrets (GROQ)
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.error("❌ GROQ_API_KEY not found in secrets!")
    st.info("Add `GROQ_API_KEY = \"gsk_xxxxx\"` in Streamlit Cloud Settings → Secrets")
    st.stop()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "tools" in msg and msg["tools"]:
            with st.expander("🔧 Tools Called"):
                for tool in msg["tools"]:
                    st.caption(f"📞 {tool['tool']}: `{json.dumps(tool['input'])}`")

# Handle input
if "sample_query" in st.session_state:
    query = st.session_state.sample_query
    del st.session_state.sample_query
else:
    query = st.chat_input("Ask: 'Check order ORD-12345' or 'I want a refund...'")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)
    
    with st.chat_message("assistant"):
        with st.spinner("🤔 Agent thinking and calling tools..."):
            agent = CustomerSupportAgent(api_key)
            result = agent.process_message(query, st.session_state.session_id, st.session_state.messages[:-1])
            
            st.write(result["response"])
            
            if result["tools_called"]:
                with st.expander("🔧 Tools Called"):
                    for i, tool in enumerate(result["tools_called"]):
                        st.markdown(f"**Tool:** `{tool['tool']}`")
                        st.markdown(f"**Input:** `{json.dumps(tool['input'])}`")
                        if i < len(result["tool_results"]):
                            st.markdown("**Result:**")
                            st.json(result["tool_results"][i]["result"])
                        st.markdown("---")
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["response"],
                "tools": result["tools_called"]
            })
    
    st.rerun()

st.markdown("---")
st.caption("🔍 Built with **Groq Llama 3 + Tool Calling** | 100% Free")