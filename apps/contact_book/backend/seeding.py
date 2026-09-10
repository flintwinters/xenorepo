"""Deterministic, repeatable sample contact generation."""

from uuid import NAMESPACE_URL, uuid5

from apps.contact_book.backend.database import ContactCreate, ContactError, ContactStore

FIRST_NAMES = ("Avery", "Blair", "Casey", "Drew", "Emery", "Frankie", "Harper", "Jamie",
    "Kai", "Lane", "Morgan", "Nico", "Parker", "Quinn", "Reese", "Sage")
LAST_NAMES = ("Adler", "Brooks", "Chen", "Diaz", "Ellis", "Foster", "Gupta", "Hayes",
    "Ito", "Jones", "Khan", "Lopez", "Morris", "Nguyen", "Owens", "Patel", "Rivera")
COMPANIES = ("Acorn Labs", "Bluebird Studio", "Cedar Works", "Drift Systems", "Ember & Co",
    "Fieldstone", "Good Harbor", "Juniper Group")
CITIES = ("Atlanta", "Austin", "Boston", "Chicago", "Denver", "New York", "Portland", "Seattle")
ROLES = ("Designer", "Engineer", "Founder", "Operations Lead", "Product Manager", "Researcher")
TAGS = ("client", "friend", "partner", "prospect", "team", "vendor")


def generated_contact(index: int) -> tuple[str, ContactCreate]:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index // len(FIRST_NAMES) + index * 3) % len(LAST_NAMES)]
    identity = str(uuid5(NAMESPACE_URL, f"xenorepo/contact-book/{index}"))
    return identity, ContactCreate(name=f"{first} {last}",
        email=f"{first}.{last}.{index + 1}@example.test".lower(),
        phone=f"+1 555 {100 + index % 900:03d} {1000 + index % 9000:04d}",
        company=COMPANIES[index % len(COMPANIES)], job_title=ROLES[index % len(ROLES)],
        city=CITIES[index % len(CITIES)], tags=[TAGS[index % len(TAGS)]])


def seed_contacts(store: ContactStore, count: int = 500) -> int:
    created = 0
    for index in range(count):
        identity, contact = generated_contact(index)
        try:
            store.create(contact, identity=identity)
            created += 1
        except ContactError:
            continue
    return created
