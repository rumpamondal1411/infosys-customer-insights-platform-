"""
Removes the customers (and their orders / wishlist items / product views)
that were added by `add_more_customers.py` — and ONLY those.

It never touches:
  - any customer you registered yourself through the app
  - any customer created by the original seed_data.py run
  - any vendor or product, ever

How it decides what to delete (in order of preference):
  1. If `_added_customer_batches.json` exists (written automatically by
     add_more_customers.py each time it runs), it deletes the customers
     from the most recent batch recorded there. This is exact — no
     guessing involved.
  2. If that file doesn't exist (e.g. you ran an older version of
     add_more_customers.py before this tracking was added), it falls back
     to deleting the N most-recently-created customers, ordered by
     `created_at` — you'll be shown exactly who that is and asked to
     confirm before anything is deleted.

Usage:
    # Preview only — shows who WOULD be deleted, deletes nothing:
    python -m app.utils.remove_added_customers --dry-run

    # Delete the most recent tracked batch (asks for confirmation):
    python -m app.utils.remove_added_customers

    # No tracking file found / want to delete the last N customers instead:
    python -m app.utils.remove_added_customers --last 100

    # Skip the confirmation prompt (e.g. for scripting):
    python -m app.utils.remove_added_customers --yes
"""
import argparse
import json
from pathlib import Path

from app.database import SessionLocal, init_db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.product_view import ProductView
from app.models.wishlist import Wishlist

_BATCH_LOG_PATH = Path(__file__).parent / "_added_customer_batches.json"


def _load_last_batch_ids():
    if not _BATCH_LOG_PATH.exists():
        return None
    try:
        batches = json.loads(_BATCH_LOG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not batches:
        return None
    return batches[-1]["customer_ids"], batches


def _pop_last_batch(batches):
    """Removes the most recent batch entry from the tracking file after
    it's been successfully deleted, so re-running doesn't try to delete
    the same (now-gone) customers again."""
    batches = batches[:-1]
    if batches:
        _BATCH_LOG_PATH.write_text(json.dumps(batches, indent=2))
    else:
        _BATCH_LOG_PATH.unlink(missing_ok=True)


def _select_customers_by_ids(db, customer_ids):
    return (
        db.query(Customer)
        .filter(Customer.id.in_(customer_ids))
        .order_by(Customer.created_at.desc())
        .all()
    )


def _select_last_n_customers(db, n):
    return (
        db.query(Customer)
        .order_by(Customer.created_at.desc(), Customer.id.desc())
        .limit(n)
        .all()
    )


def delete_customers(db, customers):
    """Deletes the given customers along with every row that references
    them (orders/transactions, wishlist entries, product-view history)."""
    customer_ids = [c.id for c in customers]
    if not customer_ids:
        return 0

    tx_deleted = (
        db.query(Transaction)
        .filter(Transaction.customer_id.in_(customer_ids))
        .delete(synchronize_session=False)
    )
    view_deleted = (
        db.query(ProductView)
        .filter(ProductView.customer_id.in_(customer_ids))
        .delete(synchronize_session=False)
    )
    wishlist_deleted = (
        db.query(Wishlist)
        .filter(Wishlist.customer_id.in_(customer_ids))
        .delete(synchronize_session=False)
    )
    customers_deleted = (
        db.query(Customer)
        .filter(Customer.id.in_(customer_ids))
        .delete(synchronize_session=False)
    )

    db.commit()
    print(f"  -> {tx_deleted} order(s)/transaction(s) deleted")
    print(f"  -> {view_deleted} product view(s) deleted")
    print(f"  -> {wishlist_deleted} wishlist item(s) deleted")
    print(f"  -> {customers_deleted} customer(s) deleted")
    return customers_deleted


def run(last_n=None, dry_run=False, skip_confirm=False):
    init_db()
    db = SessionLocal()
    try:
        batches = None
        if last_n:
            customers = _select_last_n_customers(db, last_n)
            source = f"the last {last_n} customers created (by signup date)"
        else:
            loaded = _load_last_batch_ids()
            if loaded is None:
                print(
                    "No batch tracking file found (_added_customer_batches.json).\n"
                    "This likely means add_more_customers.py was run before this tracking "
                    "existed.\nRe-run this command with --last <N>, e.g.:\n\n"
                    "    python -m app.utils.remove_added_customers --last 100\n"
                )
                return
            customer_ids, batches = loaded
            customers = _select_customers_by_ids(db, customer_ids)
            source = "the most recently recorded add_more_customers.py batch"

        if not customers:
            print("Nothing to delete — no matching customers found.")
            return

        print(f"About to delete {len(customers)} customer(s) from {source}:\n")
        for c in customers[:10]:
            print(f"   - [{c.id}] {c.name} <{c.email}>")
        if len(customers) > 10:
            print(f"   ... and {len(customers) - 10} more")

        if dry_run:
            print("\nDry run only — nothing was deleted.")
            return

        if not skip_confirm:
            answer = input(f"\nType 'yes' to permanently delete these {len(customers)} customer(s) and their orders: ")
            if answer.strip().lower() != "yes":
                print("Cancelled — nothing was deleted.")
                return

        deleted_count = delete_customers(db, customers)

        if batches is not None:
            _pop_last_batch(batches)

        print(f"\nDone. {deleted_count} customer(s) and their orders removed. "
              f"Everything else (your own customers, vendors, products) is untouched.")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--last", type=int, default=None,
                         help="Delete the N most-recently-created customers instead of using the tracked batch.")
    parser.add_argument("--dry-run", action="store_true", help="Show who would be deleted without deleting anything.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    run(last_n=args.last, dry_run=args.dry_run, skip_confirm=args.yes)