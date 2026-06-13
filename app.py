import streamlit as st
import os
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import anthropic

# ---------- Database Setup (SQLite - No external database needed) ----------
# Always use SQLite for Streamlit Cloud
DATABASE_URL = "sqlite:///./agent.db"

# Create directory for database
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
    """Get order status and shipping information"""
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
    """Check if product is in stock"""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if not product:
            return {"success": False, "error": f"Product {product_id} not found"}
        
        status = "in_stock" if product.stock_quantity > 0 else "out_of_stock"
        return {
            "success": True,
            "product_id": product.product_id,
            "product_name": product.name,
            "stock_quantity": product.stock_quantity,
            "status": status,
            "price": product.price
        }
    finally:
        db.close()

def create_support_ticket(customer_id: str, issue: str, order_id: str = None) -> dict:
    """Create a support ticket for escalation"""
    db = SessionLocal()
    try:
        ticket_count = db.query(SupportTicket).count()
        ticket_id = f"TKT-{ticket_count + 10001}"
        
        priority = "medium"
        issue_lower = issue.lower()
        if any(word in issue_lower for word in ["urgent", "escalate", "asap", "late", "delay", "complaint"]):
            priority = "high"
        
        ticket = SupportTicket(
            ticket_id=ticket_id,
            customer_id=customer_id,
            order_id=order_id,
            issue=issue,
            status="open",
            priority=priority
        )
        db.add(ticket)
        db.commit()
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "priority": priority,
            "message": f"Support ticket {ticket_id} created with {priority} priority"
        }
    finally:
        db.close()

def process_refund(order_id: str, customer_id: str, reason: str) -> dict:
    """Process refund for eligible order"""
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
            return {
                "success": True,
                "order_id": order_id,
                "refund_amount": order.total_amount,
                "message": f"Refund of ${order.total_amount} processed for order {order_id}"
            }
        else:
            return {
                "success": False,
                "error": f"Order {order_id} is not eligible for refund. Current status: {order.status}"
            }
    finally:
        db.close()

# ---------- Tool Definitions for Claude ----------
TOOLS = [
    {
        "name": "get_order_status",
        "description": "Get the current status and shipping information for an order. Use when customer asks about their order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID like ORD-12345"}
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "check_inventory",
        "description": "Check if a product is in stock. Use when customer asks about product availability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID like P001"}
            },
            "required": ["product_id"]
        }
    },
    {
        "name": "create_support_ticket",
        "description": "Create a support ticket for escalation. Use when customer complains or wants to speak to a manager.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID like CUST-001"},
                "issue": {"type": "string", "description": "Description of the issue"},
                "order_id": {"type": "string", "description": "Related order ID (optional)", "optional": True}
            },
            "required": ["customer_id", "issue"]
        }
    },
    {
        "name": "process_refund",
        "description": "Process a refund for an eligible order. Use when customer requests a refund.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID to refund"},
                "customer_id": {"type": "string", "description": "Customer ID for verification"},
                "reason": {"type": "string", "description": "Reason for refund"}
            },
            "required": ["order_id", "customer_id", "reason"]
        }
    }
]

TOOL_FUNCTIONS = {
    "get_order_status": get_order_status,
    "check_inventory": check_inventory,
    "create_support_ticket": create_support_ticket,
    "process_refund": process_refund
}

# ---------- Agent Class ----------
class CustomerSupportAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
    
    def process_message(self, user_message: str, session_id: str, history: list) -> dict:
        system_prompt = """You are a customer support agent with access to tools.

Tools available:
- get_order_status: Check order status and shipping
- check_inventory: Check product availability  
- create_support_ticket: Create escalation ticket for complaints
- process_refund: Process refund for eligible orders

Guidelines:
1. First understand what customer needs
2. Call appropriate tool(s) to get information
3. Based on results, provide helpful response
4. Be empathetic and professional
5. Verify customer_id before processing refunds

For late orders: Check status first, then offer escalation or refund.
For refunds: Always verify customer_id matches the order.
For complaints: Create support ticket with high priority."""
        
        messages = []
        for msg in history[-10:]:
            messages.append({"role": "user" if msg["role"] == "user" else "assistant", 
                            "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        
        tools_called = []
        tool_results = []
        response_text = ""
        
        for _ in range(5):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            response_text = response.content[0].text if response.content[0].type == "text" else ""
            
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            
            if not tool_uses:
                break
            
            for tool_use in tool_uses:
                tool_name = tool_use.name
                tool_input = tool_use.input
                tool_id = tool_use.id
                
                tools_called.append({"tool": tool_name, "input": tool_input})
                
                if tool_name in TOOL_FUNCTIONS:
                    try:
                        result = TOOL_FUNCTIONS[tool_name](**tool_input)
                        tool_results.append({"tool": tool_name, "result": result})
                        result_json = json.dumps(result)
                    except Exception as e:
                        result_json = json.dumps({"error": str(e)})
                else:
                    result_json = json.dumps({"error": f"Unknown tool: {tool_name}"})
                
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": tool_id, "name": tool_name, "input": tool_input}]
                })
                messages.append({
                    "role": "user", 
                    "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": result_json}]
                })
        
        return {
            "response": response_text,
            "tools_called": tools_called,
            "tool_results": tool_results
        }

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

# Title
st.title("🤖 Autonomous Customer Support Agent")
st.markdown("""
    This AI agent can **take actions** - not just answer questions!
    - ✅ Check order status
    - ✅ Check product inventory  
    - ✅ Create support tickets
    - ✅ Process refunds
""")

# Initialize session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Get API key from secrets
api_key = st.secrets.get("ANTHROPIC_API_KEY")
if not api_key:
    st.error("❌ ANTHROPIC_API_KEY not found in secrets!")
    st.info("""
        **How to setup:**
        1. Get API key from [console.anthropic.com](https://console.anthropic.com)
        2. Go to Streamlit Cloud Settings → Secrets
        3. Add: `ANTHROPIC_API_KEY = "sk-ant-xxxxx"`
    """)
    st.stop()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "tools" in msg and msg["tools"]:
            with st.expander("🔧 Tools Called"):
                for tool in msg["tools"]:
                    st.caption(f"📞 {tool['tool']}: `{json.dumps(tool['input'])}`")

# Handle sample query
if "sample_query" in st.session_state:
    query = st.session_state.sample_query
    del st.session_state.sample_query
else:
    query = st.chat_input("Ask me something like: 'Check order ORD-12345' or 'I want a refund for ORD-12345'")

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
st.caption("🔍 Built with **Claude 3.5 Sonnet + Tool Calling** | Autonomous Agent that takes real actions")