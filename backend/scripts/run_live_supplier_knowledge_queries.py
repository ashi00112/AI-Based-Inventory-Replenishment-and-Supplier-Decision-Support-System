import sys
import json

sys.path.insert(0, r"c:\irwa project\backend")

from app.database.session import SessionLocal
from app.services.supplier_knowledge_service import resolve_supplier_knowledge

def run_live_verification():
    db = SessionLocal()
    queries = [
        "What is TechSource's MOQ and lead time for the wireless mouse?",
        "What happens if TechSource Lanka delivers late?",
        "Which suppliers provide DEMO-001?",
        "Compare supplier information for an emergency wireless mouse order.",
        "Tell me something about operations.",
    ]

    print("================================================================================")
    print("LIVE SUPPLIER KNOWLEDGE VERIFICATION")
    print("================================================================================")

    for i, q in enumerate(queries, 1):
        print(f"\n--------------------------------------------------------------------------------")
        print(f"QUERY {i}: {q}")
        print(f"--------------------------------------------------------------------------------")
        result = resolve_supplier_knowledge(query=q, db=db, top_k=3)
        analysis = result["query_analysis"]
        print(f"ANALYSIS:")
        print(f"  Intent: {analysis['intent']}")
        print(f"  Route: {analysis['route']}")
        print(f"  Confidence: {analysis['confidence']}")
        print(f"  Supplier: {analysis['supplier_name']} (ID: {analysis['supplier_id']}, Code: {analysis['supplier_code']})")
        print(f"  Product: {analysis['product_name']} (ID: {analysis['product_id']}, SKU: {analysis['sku']})")
        print(f"  Needs Clarification: {result.get('needs_clarification')}")
        print(f"  Clarification Reason: {result.get('clarification_reason')}")

        print(f"\nSTRUCTURED FACTS ({len(result['structured_facts'])} found):")
        for f in result["structured_facts"]:
            print(f"  - {f}")

        print(f"\nDOCUMENT EVIDENCE ({len(result['document_evidence'])} chunks found):")
        for doc in result["document_evidence"]:
            print(f"  - Rank {doc['rank']} | Doc ID {doc['document_id']}: '{doc['document_title']}' | Type: {doc['document_type']} | Supplier ID: {doc['supplier_id']} | Page: {doc['page_number']} | Dist: {doc['distance']:.4f}")
            print(f"    Source Type: {doc.get('source_type')} | Authority: {doc.get('authority')}")
            text_snippet = doc['text'].replace('\n', ' ')[:150]
            print(f"    Excerpt: {text_snippet}...")

    db.close()

if __name__ == "__main__":
    run_live_verification()
