"""
Wipes out ALL customers except a list you provide (your real, hand-
registered accounts) — along with every order/transaction, wishlist
entry, and browsing-history row that belonged to the deleted customers.

This is meant for the situation where your database has a mix of:
  - a handful of customers YOU registered yourself through the app
    (who haven't placed any real orders yet)
  - a bunch of fake demo customers + fake historical orders created by
    seed_data.py (and possibly a batch from add_more_customers.py)

...and you want the database to end up with ONLY your real customers,
and every customer-analytics/revenue page to show empty/zero until real
orders start coming in.

It NEVER touches:
  - vendors
  - products / categories / inventory
  - the customers you tell it to keep

By default it also deletes "guest" orders (transactions with no
customer attached at all) since those are demo noise too — pass
--keep-guest-orders if you want to leave those alone.

Usage:
    # Preview only — shows what WOULD be deleted, deletes nothing:
    python -m app.utils.wipe_demo_customers --keep "a@x.com,b@x.com,..." --dry-run

    # Actually delete everything except the listed emails (asks to confirm):
    python -m app.utils.wipe_demo_customers --keep "a@x.com,b@x.com,..."

    # Skip the confirmation prompt:
    python -m app.utils.wipe_demo_customers --keep "a@x.com,..." --yes

    # Keep guest (no-customer) orders instead of deleting them too:
    python -m app.utils.wipe_demo_customers --keep "a@x.com,..." --keep-guest-orders
"""
import argparse

from app.database import SessionLocal, init_db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.product_view import ProductView
from app.models.wishlist import Wishlist


def _normalize_emails(raw: str):
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def run(keep_emails_raw: str, dry_run: bool = False, skip_confirm: bool = False, keep_guest_orders: bool = False):
    keep_emails = _normalize_emails(keep_emails_raw)
    if not keep_emails:
        print("No emails provided to --keep — refusing to run (that would delete every customer).")
        return

    init_db()
    db = SessionLocal()
    try:
        all_customers = db.query(Customer).all()

        keep_customers = [c for c in all_customers if c.email.lower() in keep_emails]
        found_emails = {c.email.lower() for c in keep_customers}
        missing = keep_emails - found_emails
        if missing:
            print("WARNING: these emails from --keep were not found in the database "
                  "(so there's nothing to protect for them — double check spelling):")
            for m in sorted(missing):
                print(f"   - {m}")
            print()

        delete_customers = [c for c in all_customers if c.email.lower() not in keep_emails]
        delete_ids = [c.id for c in delete_customers]

        print(f"Keeping {len(keep_customers)} customer(s):")
        for c in keep_customers:
            print(f"   - [{c.id}] {c.name} <{c.email}>")

        print(f"\nAbout to delete {len(delete_customers)} customer(s) (and their orders/wishlist/history):")
        for c in delete_customers[:10]:
            print(f"   - [{c.id}] {c.name} <{c.email}>")
        if len(delete_customers) > 10:
            print(f"   ... and {len(delete_customers) - 10} more")

        guest_tx_count = db.query(Transaction).filter(Transaction.customer_id.is_(None)).count()
        if guest_tx_count:
            action = "left alone" if keep_guest_orders else "also deleted"
            print(f"\nAlso found {guest_tx_count} guest order(s) with no customer attached — these will be {action}.")

        if dry_run:
            print("\nDry run only — nothing was deleted.")
            return

        if not skip_confirm:
            answer = input(
                f"\nType 'yes' to permanently delete these {len(delete_customers)} customer(s) "
                f"and all their orders/history: "
            )
            if answer.strip().lower() != "yes":
                print("Cancelled — nothing was deleted.")
                return

        tx_deleted = 0
        if delete_ids:
            tx_deleted += (
                db.query(Transaction)
                .filter(Transaction.customer_id.in_(delete_ids))
                .delete(synchronize_session=False)
            )
        if not keep_guest_orders:
            tx_deleted += (
                db.query(Transaction)
                .filter(Transaction.customer_id.is_(None))
                .delete(synchronize_session=False)
            )

        view_deleted = 0
        wishlist_deleted = 0
        customers_deleted = 0
        if delete_ids:
            view_deleted = (
                db.query(ProductView)
                .filter(ProductView.customer_id.in_(delete_ids))
                .delete(synchronize_session=False)
            )
            wishlist_deleted = (
                db.query(Wishlist)
                .filter(Wishlist.customer_id.in_(delete_ids))
                .delete(synchronize_session=False)
            )
            customers_deleted = (
                db.query(Customer)
                .filter(Customer.id.in_(delete_ids))
                .delete(synchronize_session=False)
            )

        db.commit()

        print(f"\nDone.")
        print(f"  -> {tx_deleted} order(s)/transaction(s) deleted")
        print(f"  -> {view_deleted} product view(s) deleted")
        print(f"  -> {wishlist_deleted} wishlist item(s) deleted")
        print(f"  -> {customers_deleted} customer(s) deleted")
        print(f"\nRemaining: {len(keep_customers)} customer(s), 0 orders. "
              f"Vendors, products, and inventory were not touched.")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep", type=str, required=True,
                         help="Comma-separated list of customer emails to KEEP. Everyone else is deleted.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting anything.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    parser.add_argument("--keep-guest-orders", action="store_true",
                         help="Don't delete orders that have no customer attached.")
    args = parser.parse_args()

    run(args.keep, dry_run=args.dry_run, skip_confirm=args.yes, keep_guest_orders=args.keep_guest_orders)