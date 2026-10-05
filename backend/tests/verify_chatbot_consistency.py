import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.session import SessionLocal
from app.models.user import User
from app.services.chat_service import ChatService

def run_tests():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email="admin@smartsupply.ai").first() or db.query(User).first()
        if not user:
            print("ERROR: No user found.")
            return

        service = ChatService(db=db, user=user)

        # ---------------------------------------------------------
        # Query 1: How many Wireless Mice are reserved?
        # ---------------------------------------------------------
        c1 = service.create_conversation("Q1 - Reserved Stock")
        r1 = service.process_user_message(c1.id, "How many Wireless Mice are reserved?")
        print("\n--- QUERY 1 ---")
        print("User: How many Wireless Mice are reserved?")
        print("Intent:", r1.intent)
        print("First Sentence:", r1.answer.splitlines()[0] if r1.answer else "")
        print("Full Answer:\n" + r1.answer)
        assert "5" in r1.answer and "reserved" in r1.answer.lower(), "Q1 failed: must state 5 reserved"

        # ---------------------------------------------------------
        # Query 2: Should we replenish? (Missing product)
        # ---------------------------------------------------------
        c2 = service.create_conversation("Q2 - Missing Product")
        r2 = service.process_user_message(c2.id, "Should we replenish?")
        print("\n--- QUERY 2 ---")
        print("User: Should we replenish?")
        print("Status:", r2.status)
        print("Needs Clarification:", r2.needs_clarification)
        print("Clarification Prompt:", r2.clarification_prompt)
        print("Answer:\n" + r2.answer)
        assert r2.needs_clarification and "which product" in r2.answer.lower(), "Q2 failed: must ask which product"

        # ---------------------------------------------------------
        # Query 3: Delete the Wireless Mouse inventory. (Read-only guard)
        # ---------------------------------------------------------
        c3 = service.create_conversation("Q3 - Read Only Guard")
        r3 = service.process_user_message(c3.id, "Delete the Wireless Mouse inventory.")
        print("\n--- QUERY 3 ---")
        print("User: Delete the Wireless Mouse inventory.")
        print("Intent:", r3.intent)
        print("Answer:\n" + r3.answer)
        assert "read-only" in r3.answer.lower() or "cannot modify" in r3.answer.lower(), "Q3 failed: read-only message expected"

        # ---------------------------------------------------------
        # Query 4: What is Digital Distribution's OTIF performance?
        # ---------------------------------------------------------
        c4 = service.create_conversation("Q4 - Digital OTIF")
        r4 = service.process_user_message(c4.id, "What is Digital Distribution's OTIF performance?")
        print("\n--- QUERY 4 ---")
        print("User: What is Digital Distribution's OTIF performance?")
        print("Intent:", r4.intent)
        print("Answer:\n" + r4.answer)
        assert "98.4%" in r4.answer, "Q4 failed: 98.4% OTIF expected"

        # ---------------------------------------------------------
        # Query 5: What happens if TechSource delivers late?
        # ---------------------------------------------------------
        c5 = service.create_conversation("Q5 - TechSource Late")
        r5 = service.process_user_message(c5.id, "What happens if TechSource delivers late?")
        print("\n--- QUERY 5 ---")
        print("User: What happens if TechSource delivers late?")
        print("Intent:", r5.intent)
        print("Answer:\n" + r5.answer)
        assert "24-hour" in r5.answer and ("1.5%" in r5.answer or "penalty" in r5.answer), "Q5 failed: 24h notice / penalty expected"

        # ---------------------------------------------------------
        # Setup active decision for follow-ups (Q6, Q7, Q8, Q9, Q12, Q13)
        # ---------------------------------------------------------
        c_active = service.create_conversation("Active Decision Conversation")
        r_step1 = service.process_user_message(c_active.id, "Should we replenish Wireless Mouse?")
        # Now provide horizon 14 days
        r_step2 = service.process_user_message(c_active.id, "14 days")

        # ---------------------------------------------------------
        # Query 6: How did you calculate the recommended order quantity?
        # ---------------------------------------------------------
        r6 = service.process_user_message(c_active.id, "How did you calculate the recommended order quantity?")
        print("\n--- QUERY 6 ---")
        print("User: How did you calculate the recommended order quantity?")
        print("Intent:", r6.intent)
        print("Answer:\n" + r6.answer)
        assert "131" in r6.answer and ("84" in r6.answer or "effective" in r6.answer.lower()), "Q6 failed: 131 units and effective 84 expected"

        # ---------------------------------------------------------
        # Query 7: Why are incoming units included in the order quantity?
        # ---------------------------------------------------------
        r7 = service.process_user_message(c_active.id, "Why are incoming units included in the order quantity?")
        print("\n--- QUERY 7 ---")
        print("User: Why are incoming units included in the order quantity?")
        print("Intent:", r7.intent)
        print("Decision Summary:", r7.decision_summary)
        print("Answer:\n" + r7.answer)
        assert r7.decision_summary is None, "Q7 failed: recommendation card must NOT be shown"
        assert "pipeline" in r7.answer.lower() or "incoming" in r7.answer.lower(), "Q7 failed: pipeline explanation expected"

        # ---------------------------------------------------------
        # Query 8: Why aren't incoming units used to delay the stockout date?
        # ---------------------------------------------------------
        r8 = service.process_user_message(c_active.id, "Why aren't incoming units used to delay the stockout date?")
        print("\n--- QUERY 8 ---")
        print("User: Why aren't incoming units used to delay the stockout date?")
        print("Intent:", r8.intent)
        print("Decision Summary:", r8.decision_summary)
        print("Answer:\n" + r8.answer)
        assert r8.decision_summary is None, "Q8 failed: recommendation card must NOT be shown"
        assert "arrival date" in r8.answer.lower() or "timeline" in r8.answer.lower(), "Q8 failed: arrival date / timeline explanation expected"

        # ---------------------------------------------------------
        # Query 9: What is the stockout risk? (Wireless Mouse + 14-day context)
        # ---------------------------------------------------------
        r9 = service.process_user_message(c_active.id, "What is the stockout risk?")
        print("\n--- QUERY 9 ---")
        print("User: What is the stockout risk?")
        print("Intent:", r9.intent)
        print("Stockout Summary:", r9.stockout_summary)
        print("Answer:\n" + r9.answer)
        assert "HIGH" in r9.answer.upper(), "Q9 failed: HIGH risk expected"
        assert "BREACHED NOW" in r9.answer or "0 days" in r9.answer, "Q9 failed: BREACHED NOW expected"

        # ---------------------------------------------------------
        # Query 10: Who supplies Wireless Mouse? then Which one can deliver fastest?
        # ---------------------------------------------------------
        c10 = service.create_conversation("Q10 - Supplier Fast")
        r10_a = service.process_user_message(c10.id, "Who supplies Wireless Mouse?")
        r10_b = service.process_user_message(c10.id, "Which one can deliver fastest?")
        print("\n--- QUERY 10 ---")
        print("User: Who supplies Wireless Mouse? -> Which one can deliver fastest?")
        print("Intent:", r10_b.intent)
        print("Answer:\n" + r10_b.answer)
        assert "Digital Distribution" in r10_b.answer and "2-day" in r10_b.answer, "Q10 failed: Digital Distribution 2-day expected"

        # ---------------------------------------------------------
        # Query 11: What happens to the forecast if I use 7 days instead of 14 days?
        # ---------------------------------------------------------
        r11 = service.process_user_message(c_active.id, "What happens to the forecast if I use 7 days instead of 14 days?")
        print("\n--- QUERY 11 ---")
        print("User: What happens to the forecast if I use 7 days instead of 14 days?")
        print("Intent:", r11.intent)
        print("Decision Summary:", r11.decision_summary)
        print("Answer:\n" + r11.answer)
        assert r11.decision_summary is None, "Q11 failed: no supplier recommendation card"
        assert "7 days" in r11.answer and "reduces" in r11.answer.lower(), "Q11 failed: forecast delta expected"

        # ---------------------------------------------------------
        # Query 12: Why was Digital selected?
        # ---------------------------------------------------------
        r12 = service.process_user_message(c_active.id, "Why was Digital selected?")
        print("\n--- QUERY 12 ---")
        print("User: Why was Digital selected?")
        print("Intent:", r12.intent)
        print("Answer:\n" + r12.answer)
        assert "Digital" in r12.answer and ("window" in r12.answer.lower() or "lead time" in r12.answer.lower()), "Q12 failed: selection explanation expected"

        # ---------------------------------------------------------
        # Query 13: Show me the evidence.
        # ---------------------------------------------------------
        r13 = service.process_user_message(c_active.id, "Show me the evidence.")
        print("\n--- QUERY 13 ---")
        print("User: Show me the evidence.")
        print("Intent:", r13.intent)
        print("Sources count:", len(r13.sources))
        print("Answer:\n" + r13.answer)
        assert len(r13.sources) > 0, "Q13 failed: sources expected"

        # Clean up test conversations
        for c in [c1, c2, c3, c4, c5, c_active, c10]:
            service.delete_conversation(c.id)

        print("\n==========================================")
        print("ALL 13 TEST QUERIES PASSED SUCCESSFULLY!")
        print("==========================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
