import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from app.database.session import SessionLocal
from app.models.user import User
from app.models.chat import ChatConversation
from app.services.chat_service import ChatService

def main():
    db = SessionLocal()
    log_f = open("tests/live_cases_output.txt", "w", encoding="utf-8")

    def log_print(*args, **kwargs):
        print(*args, **kwargs)
        print(*args, **kwargs, file=log_f, flush=True)

    try:
        user = db.query(User).filter_by(email="admin@smartsupply.ai").first() or db.query(User).first()
        if not user:
            log_print("No user found.")
            return

        service = ChatService(db=db, user=user)

        # CASE A
        conv_a = service.create_conversation("Case A - Inventory")
        res_a = service.process_user_message(conv_a.id, "How many Wireless Mice are available?")
        log_print("=== CASE A ===")
        log_print("Intent:", res_a.intent)
        log_print("Status:", res_a.status)
        log_print("Decision Summary:", res_a.decision_summary)
        log_print("Answer:\n" + res_a.answer)
        log_print()

        # CASE B
        conv_b = service.create_conversation("Case B - Supplier MOQ")
        res_b = service.process_user_message(conv_b.id, "What is TechSource's MOQ for Wireless Mouse?")
        log_print("=== CASE B ===")
        log_print("Intent:", res_b.intent)
        log_print("Status:", res_b.status)
        log_print("Answer:\n" + res_b.answer)
        log_print()

        # CASE C
        conv_c = service.create_conversation("Case C - SLA Question")
        res_c = service.process_user_message(conv_c.id, "What happens if TechSource delivers late?")
        log_print("=== CASE C ===")
        log_print("Intent:", res_c.intent)
        log_print("Sources count:", len(res_c.sources))
        log_print("Answer:\n" + res_c.answer)
        log_print()

        # CASE D
        conv_d = service.create_conversation("Case D - Horizon Clarification & Decision")
        res_d1 = service.process_user_message(conv_d.id, "Should we replenish Wireless Mouse?")
        log_print("=== CASE D (Turn 1) ===")
        log_print("Status:", res_d1.status)
        log_print("Needs Clarification:", res_d1.needs_clarification)
        log_print("Clarification Options:", [opt.label for opt in (res_d1.clarification_options or [])])
        log_print("Answer:\n" + res_d1.answer)
        log_print()

        res_d2 = service.process_user_message(conv_d.id, "14 days")
        log_print("=== CASE D (Turn 2 - Horizon 14 days) ===")
        log_print("Intent:", res_d2.intent)
        log_print("Status:", res_d2.status)
        log_print("Selected Supplier:", res_d2.decision_summary.selected_supplier_name if res_d2.decision_summary else None)
        log_print("Answer:\n" + res_d2.answer)
        log_print()

        # CASE E (Follow-up in Conv D)
        res_e = service.process_user_message(conv_d.id, "Why was Digital selected?")
        log_print("=== CASE E ===")
        log_print("Intent:", res_e.intent)
        log_print("Answer:\n" + res_e.answer)
        log_print()

        # CASE F (Follow-up in Conv D)
        res_f = service.process_user_message(conv_d.id, "Show me the evidence.")
        log_print("=== CASE F ===")
        log_print("Intent:", res_f.intent)
        log_print("Sources count:", len(res_f.sources))
        log_print("Answer:\n" + res_f.answer)
        log_print()

        # CASE G (New Conversation)
        conv_g = service.create_conversation("Case G - Explicit Horizon")
        res_g = service.process_user_message(conv_g.id, "Should we replenish Wireless Mouse over the next 7 days?")
        log_print("=== CASE G ===")
        log_print("Intent:", res_g.intent)
        log_print("Status:", res_g.status)
        log_print("Forecast Horizon:", res_g.forecast_horizon_days)
        log_print("Selected Supplier:", res_g.decision_summary.selected_supplier_name if res_g.decision_summary else None)
        log_print("Answer:\n" + res_g.answer)
        log_print()

        # Clean up test conversations
        for c in [conv_a, conv_b, conv_c, conv_d, conv_g]:
            service.delete_conversation(c.id)

    finally:
        log_f.close()
        db.close()


if __name__ == "__main__":
    main()
