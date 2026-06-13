# 🤖 Autonomous Agent with Tool Calling

AI agent that doesn't just answer questions – it takes real actions like checking orders, processing refunds, and creating support tickets.

## Live Demo
[Press here for live demo!](https://autonomousagentai-rzxksdmwwmb5mvvvqiqvew.streamlit.app/)

## Features
- Chat interface with memory
- Tool calling (order status, inventory, refunds, tickets)
- Multi-step reasoning (check order → process refund → create ticket)
- Shows which tools were called and their results
- 100% free (no OpenAI required)

## Tech Stack
- Streamlit (frontend)
- Groq Llama 3 (free LLM)
- SQLite (database)
- SQLAlchemy (ORM)

## How to Run Locally
1. Clone repo
2. Install requirements: `pip install -r requirements.txt`
3. Create `.streamlit/secrets.toml` with your Groq API key
4. Run `streamlit run app.py`

## Example Questions
- "Check order ORD-12345 status"
- "Is product P004 in stock?"
- "My order ORD-12345 is late! I want a refund. My customer ID is CUST-001"
- "I want to speak to a manager about my late order. Customer ID: CUST-001"
- "Check inventory for product P005"
- "What is the status of order ORD-12346?"
- "Process refund for order ORD-12347, customer CUST-002"
- "Create a support ticket for delayed shipment, customer CUST-003"