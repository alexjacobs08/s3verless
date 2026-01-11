"""Fake data generation for S3verless models."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Type, get_args, get_origin
import uuid
import random
import string

from pydantic import EmailStr
from pydantic.fields import FieldInfo

from s3verless.core.base import BaseS3Model


# Try to import Faker, but provide fallback if not available
try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False
    Faker = None  # type: ignore


class DataGenerator:
    """Generate fake data based on Pydantic field types.

    This class generates appropriate fake data for model fields based on
    field names and type annotations. It uses the Faker library when available,
    falling back to basic random generation otherwise.
    """

    def __init__(self, locale: str = "en_US"):
        """Initialize the data generator.

        Args:
            locale: Locale for Faker data generation (e.g., "en_US", "de_DE")
        """
        self.locale = locale
        if FAKER_AVAILABLE:
            self.fake = Faker(locale)
        else:
            self.fake = None

    def generate_for_field(self, field_name: str, field_info: FieldInfo) -> Any:
        """Generate appropriate fake data based on field name and type.

        Args:
            field_name: The name of the field
            field_info: Pydantic FieldInfo object with type information

        Returns:
            Generated fake data appropriate for the field
        """
        annotation = field_info.annotation

        # Handle Optional types by extracting the inner type
        origin = get_origin(annotation)
        if origin is type(None) or annotation is type(None):
            return None

        # Handle Union types (including Optional which is Union[X, None])
        if origin is not None:
            args = get_args(annotation)
            # Filter out None from Union args
            non_none_args = [arg for arg in args if arg is not type(None)]
            if non_none_args:
                annotation = non_none_args[0]

        # Name-based heuristics (these take priority)
        name_lower = field_name.lower()

        # Email fields
        if "email" in name_lower or annotation is EmailStr:
            return self._generate_email()

        # Name fields
        if name_lower == "name" or name_lower == "full_name":
            return self._generate_name()
        if "first_name" in name_lower:
            return self._generate_first_name()
        if "last_name" in name_lower:
            return self._generate_last_name()
        if "username" in name_lower:
            return self._generate_username()

        # Title/description fields
        if "title" in name_lower:
            return self._generate_title()
        if "description" in name_lower or "content" in name_lower or "body" in name_lower:
            return self._generate_paragraph()
        if "bio" in name_lower or "summary" in name_lower:
            return self._generate_sentence()

        # Numeric fields
        if "price" in name_lower or "cost" in name_lower or "amount" in name_lower:
            return self._generate_price()
        if "quantity" in name_lower or "count" in name_lower or "stock" in name_lower:
            return self._generate_int(0, 1000)
        if "age" in name_lower:
            return self._generate_int(18, 80)
        if "rating" in name_lower or "score" in name_lower:
            return self._generate_float(0, 5, 1)

        # URL fields
        if "url" in name_lower or "link" in name_lower:
            return self._generate_url()
        if "image" in name_lower or "avatar" in name_lower or "photo" in name_lower:
            return self._generate_image_url()

        # Contact fields
        if "phone" in name_lower or "mobile" in name_lower:
            return self._generate_phone()
        if "address" in name_lower:
            return self._generate_address()
        if "city" in name_lower:
            return self._generate_city()
        if "country" in name_lower:
            return self._generate_country()
        if "zip" in name_lower or "postal" in name_lower:
            return self._generate_zipcode()

        # Company fields
        if "company" in name_lower or "organization" in name_lower:
            return self._generate_company()
        if "job" in name_lower or "position" in name_lower or "role" in name_lower:
            return self._generate_job_title()

        # Category/tag fields
        if "category" in name_lower or "type" in name_lower:
            return self._generate_category()
        if "tag" in name_lower:
            return self._generate_tag()

        # Date/time fields
        if "date" in name_lower or "day" in name_lower:
            return self._generate_date()

        # Boolean fields with common names
        if name_lower.startswith("is_") or name_lower.startswith("has_"):
            return self._generate_bool()

        # Type-based fallbacks
        return self._generate_for_type(annotation)

    def _generate_for_type(self, annotation: Any) -> Any:
        """Generate data based on type annotation.

        Args:
            annotation: The type annotation

        Returns:
            Generated data for the type
        """
        # Handle origin types (List, Dict, etc.)
        origin = get_origin(annotation)
        if origin is list:
            args = get_args(annotation)
            item_type = args[0] if args else str
            return [self._generate_for_type(item_type) for _ in range(random.randint(1, 5))]
        if origin is dict:
            return {}
        if origin is set:
            args = get_args(annotation)
            item_type = args[0] if args else str
            return {self._generate_for_type(item_type) for _ in range(random.randint(1, 3))}

        # Basic types
        if annotation is str:
            return self._generate_word()
        if annotation is int:
            return self._generate_int(0, 100)
        if annotation is float:
            return self._generate_float(0, 100, 2)
        if annotation is bool:
            return self._generate_bool()
        if annotation is Decimal:
            return Decimal(str(round(random.uniform(0, 100), 2)))
        if annotation is datetime:
            return self._generate_datetime()
        if annotation is date:
            return self._generate_date()
        if annotation is uuid.UUID:
            return uuid.uuid4()
        if annotation is EmailStr:
            return self._generate_email()

        # Default fallback
        return self._generate_word()

    def generate_instance(self, model_class: Type[BaseS3Model]) -> dict:
        """Generate a complete fake instance of a model.

        Args:
            model_class: The model class to generate data for

        Returns:
            Dictionary with generated field values
        """
        data = {}
        for field_name, field_info in model_class.model_fields.items():
            # Skip auto-generated fields
            if field_name in ("id", "created_at", "updated_at"):
                continue
            # Skip private fields
            if field_name.startswith("_"):
                continue
            # Skip fields with defaults if they're not required
            if not field_info.is_required() and field_info.default is not None:
                continue

            value = self.generate_for_field(field_name, field_info)
            if value is not None:
                data[field_name] = value
        return data

    def generate_instances(
        self, model_class: Type[BaseS3Model], count: int = 10
    ) -> list[dict]:
        """Generate multiple fake instances of a model.

        Args:
            model_class: The model class to generate data for
            count: Number of instances to generate

        Returns:
            List of dictionaries with generated field values
        """
        return [self.generate_instance(model_class) for _ in range(count)]

    # Private generator methods with Faker fallbacks

    def _generate_email(self) -> str:
        if self.fake:
            return self.fake.email()
        username = ''.join(random.choices(string.ascii_lowercase, k=8))
        domain = random.choice(["example.com", "test.com", "email.com"])
        return f"{username}@{domain}"

    def _generate_name(self) -> str:
        if self.fake:
            return self.fake.name()
        first = ''.join(random.choices(string.ascii_lowercase, k=5)).capitalize()
        last = ''.join(random.choices(string.ascii_lowercase, k=7)).capitalize()
        return f"{first} {last}"

    def _generate_first_name(self) -> str:
        if self.fake:
            return self.fake.first_name()
        return ''.join(random.choices(string.ascii_lowercase, k=5)).capitalize()

    def _generate_last_name(self) -> str:
        if self.fake:
            return self.fake.last_name()
        return ''.join(random.choices(string.ascii_lowercase, k=7)).capitalize()

    def _generate_username(self) -> str:
        if self.fake:
            return self.fake.user_name()
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    def _generate_title(self) -> str:
        if self.fake:
            return self.fake.sentence(nb_words=4).rstrip('.')
        words = ['The', 'A', 'My', 'Your', 'Our']
        nouns = ['Product', 'Item', 'Thing', 'Article', 'Post']
        adjs = ['Great', 'New', 'Best', 'Top', 'Amazing']
        return f"{random.choice(words)} {random.choice(adjs)} {random.choice(nouns)}"

    def _generate_sentence(self) -> str:
        if self.fake:
            return self.fake.sentence()
        words = ['Lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur',
                 'adipiscing', 'elit', 'sed', 'do', 'eiusmod', 'tempor']
        return ' '.join(random.choices(words, k=random.randint(5, 10))).capitalize() + '.'

    def _generate_paragraph(self) -> str:
        if self.fake:
            return self.fake.paragraph()
        return ' '.join(self._generate_sentence() for _ in range(3))

    def _generate_word(self) -> str:
        if self.fake:
            return self.fake.word()
        return ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 8)))

    def _generate_price(self) -> float:
        return round(random.uniform(1.0, 999.99), 2)

    def _generate_int(self, min_val: int = 0, max_val: int = 100) -> int:
        return random.randint(min_val, max_val)

    def _generate_float(
        self, min_val: float = 0, max_val: float = 100, precision: int = 2
    ) -> float:
        return round(random.uniform(min_val, max_val), precision)

    def _generate_bool(self) -> bool:
        return random.choice([True, False])

    def _generate_url(self) -> str:
        if self.fake:
            return self.fake.url()
        domain = ''.join(random.choices(string.ascii_lowercase, k=8))
        return f"https://www.{domain}.com"

    def _generate_image_url(self) -> str:
        width = random.choice([200, 400, 600, 800])
        height = random.choice([200, 400, 600, 800])
        return f"https://picsum.photos/{width}/{height}"

    def _generate_phone(self) -> str:
        if self.fake:
            return self.fake.phone_number()
        return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"

    def _generate_address(self) -> str:
        if self.fake:
            return self.fake.address().replace('\n', ', ')
        num = random.randint(1, 9999)
        street = ''.join(random.choices(string.ascii_lowercase, k=6)).capitalize()
        suffix = random.choice(['St', 'Ave', 'Rd', 'Blvd', 'Dr'])
        return f"{num} {street} {suffix}"

    def _generate_city(self) -> str:
        if self.fake:
            return self.fake.city()
        cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix',
                  'San Diego', 'Dallas', 'San Jose', 'Austin', 'Seattle']
        return random.choice(cities)

    def _generate_country(self) -> str:
        if self.fake:
            return self.fake.country()
        countries = ['United States', 'Canada', 'United Kingdom', 'Germany',
                     'France', 'Australia', 'Japan', 'Brazil', 'India', 'Mexico']
        return random.choice(countries)

    def _generate_zipcode(self) -> str:
        if self.fake:
            return self.fake.zipcode()
        return ''.join(random.choices(string.digits, k=5))

    def _generate_company(self) -> str:
        if self.fake:
            return self.fake.company()
        prefixes = ['Tech', 'Global', 'United', 'First', 'Prime']
        suffixes = ['Corp', 'Inc', 'LLC', 'Solutions', 'Industries']
        name = ''.join(random.choices(string.ascii_lowercase, k=5)).capitalize()
        return f"{random.choice(prefixes)} {name} {random.choice(suffixes)}"

    def _generate_job_title(self) -> str:
        if self.fake:
            return self.fake.job()
        levels = ['Senior', 'Junior', 'Lead', 'Chief', 'Staff']
        roles = ['Engineer', 'Manager', 'Developer', 'Designer', 'Analyst']
        return f"{random.choice(levels)} {random.choice(roles)}"

    def _generate_category(self) -> str:
        categories = ['Electronics', 'Clothing', 'Home', 'Sports', 'Books',
                      'Toys', 'Health', 'Automotive', 'Garden', 'Food']
        return random.choice(categories)

    def _generate_tag(self) -> str:
        tags = ['featured', 'popular', 'new', 'sale', 'trending',
                'limited', 'exclusive', 'hot', 'best-seller', 'recommended']
        return random.choice(tags)

    def _generate_date(self) -> date:
        if self.fake:
            return self.fake.date_object()
        days_ago = random.randint(0, 365)
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()

    def _generate_datetime(self) -> datetime:
        if self.fake:
            return self.fake.date_time(tzinfo=timezone.utc)
        days_ago = random.randint(0, 365)
        hours_ago = random.randint(0, 23)
        return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
