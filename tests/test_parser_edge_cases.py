"""Comprehensive edge case tests for openlattice/parser.py and generators."""

import ast
import sys
import traceback

sys.path.insert(0, ".")

from openlattice.generators.app_gen import generate as app_generate
from openlattice.generators.routes_gen import generate as routes_generate
from openlattice.generators.schemas_gen import generate as schemas_generate
from openlattice.generators.sqlalchemy_gen import generate as sqlalchemy_generate
from openlattice.parser import parse_string

results = []


def run_test(number, name, fn):
    print(f"\n--- Test {number}: {name} ---")
    try:
        fn()
        results.append((number, name, "PASS"))
        print("  PASS")
    except Exception as e:
        results.append((number, name, "FAIL"))
        print(f"  FAIL: {e}")
        traceback.print_exc()
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Test 1: All 5 resource types
# ---------------------------------------------------------------------------
def test_1():
    src = """
resource "lattice_entity" "user" {
  name = "User"
  fields = {
    id   = "uuid"
    name = "string"
    age  = "int"
  }
}
resource "lattice_api" "get_user" {
  name   = "GetUser"
  method = "GET"
  path   = "/users/{id}"
  output = lattice_entity.user.name
}
resource "lattice_event" "user_login" {
  name = "UserLogin"
  payload = {
    user_id = "uuid"
    ip      = "string"
  }
}
resource "lattice_workflow" "onboarding" {
  name  = "Onboarding"
  steps = ["send_welcome", "setup_profile", "notify_admin"]
}
resource "lattice_queue" "welcome_email" {
  name    = "welcome_email"
  retries = 3
}
"""
    spec = parse_string(src)
    assert len(spec.entities) == 1, f"Expected 1 entity, got {len(spec.entities)}"
    assert len(spec.apis) == 1, f"Expected 1 api, got {len(spec.apis)}"
    assert len(spec.events) == 1, f"Expected 1 event, got {len(spec.events)}"
    assert len(spec.workflows) == 1, f"Expected 1 workflow, got {len(spec.workflows)}"
    assert len(spec.queues) == 1, f"Expected 1 queue, got {len(spec.queues)}"
    assert spec.entities[0].name == "User"
    assert spec.entities[0].fields[0].name == "id"
    assert spec.entities[0].fields[0].type == "uuid"
    assert spec.apis[0].name == "GetUser"
    assert spec.apis[0].method == "GET"
    assert spec.apis[0].path == "/users/{id}"
    assert spec.apis[0].output_entity == "User"
    assert spec.events[0].name == "UserLogin"
    assert spec.workflows[0].name == "Onboarding"
    assert [s.name for s in spec.workflows[0].steps] == [
        "send_welcome",
        "setup_profile",
        "notify_admin",
    ]
    assert spec.queues[0].name == "welcome_email"
    assert spec.queues[0].retries == 3


# ---------------------------------------------------------------------------
# Test 2: Comments, blank lines, and indentation
# ---------------------------------------------------------------------------
def test_2():
    src = """

# Leading comment
# Multi-line
# comment block

  resource "lattice_entity" "post" {
  # inline comment inside block
    name = "Post"
    fields = {
      # comment between fields
      title = "string"
      body  = "string"
    }
  }

  resource "lattice_api" "create_post" {
    name   = "CreatePost"
    method = "POST"
    path   = "/posts"
    input  = lattice_entity.post.name
    output = lattice_entity.post.name
  }

# Trailing comment

"""
    spec = parse_string(src)
    assert len(spec.entities) == 1
    assert len(spec.apis) == 1
    assert spec.entities[0].name == "Post"
    assert len(spec.entities[0].fields) == 2
    assert spec.apis[0].name == "CreatePost"


# ---------------------------------------------------------------------------
# Test 3: Arrays with mixed types
# ---------------------------------------------------------------------------
def test_3():
    """Mixed-type array parsing, exercised via lattice_api.publishes (a loosely-typed
    list attribute) — workflow.steps is now structurally validated (see IR enrichment,
    issue #8), so it's no longer the right vehicle for testing raw array/value parsing."""
    src = """
resource "lattice_api" "mixed" {
  name      = "Mixed"
  method    = "POST"
  path      = "/mixed"
  publishes = ["alpha", 42, "beta", 3.14, "gamma", 0]
}
"""
    spec = parse_string(src)
    steps = spec.apis[0].publishes
    assert len(steps) == 6, f"Expected 6 items, got {len(steps)}"
    assert steps[0] == "alpha", f"Expected 'alpha', got {steps[0]}"
    assert steps[1] == 42, f"Expected 42, got {steps[1]}"
    assert isinstance(steps[1], int), f"steps[1] is {type(steps[1]).__name__}, expected int"
    assert steps[2] == "beta"
    assert steps[3] == 3.14, f"Expected 3.14, got {steps[3]}"
    assert isinstance(steps[3], float), f"steps[3] is {type(steps[3]).__name__}, expected float"
    assert steps[4] == "gamma"
    assert steps[5] == 0, f"Expected 0, got {steps[5]}"
    assert isinstance(steps[5], int), f"steps[5] is {type(steps[5]).__name__}, expected int"
    print("        Mixed array types verified: str, int, str, float, str, int")


# ---------------------------------------------------------------------------
# Test 4: Nested object values
# ---------------------------------------------------------------------------
def test_4():
    """Nested objects inside attribute values. The queue resource handles
    arbitrary extra attributes through parse_attrs -> _parse_value -> _parse_object.
    QueueDef only exposes name/retries but the parser itself must handle nesting."""
    src = """
resource "lattice_queue" "nested_test" {
  name    = "nested_test"
  retries = 3
  metadata = {
    owner = "team-a"
    config = {
      timeout = 30
      enabled = true
    }
  }
}
"""
    spec = parse_string(src)
    assert spec.queues[0].name == "nested_test"
    assert spec.queues[0].retries == 3
    # Key assertion: parser didn't crash on nested objects


# ---------------------------------------------------------------------------
# Test 5: Forward references
# ---------------------------------------------------------------------------
def test_5():
    src = """
resource "lattice_api" "get_profile" {
  name   = "GetProfile"
  method = "GET"
  path   = "/profiles/{id}"
  output = lattice_entity.profile.name
}
resource "lattice_entity" "profile" {
  name = "Profile"
  fields = {
    id     = "uuid"
    handle = "string"
    bio    = "string"
  }
}
"""
    spec = parse_string(src)
    assert len(spec.entities) == 1
    assert len(spec.apis) == 1
    assert spec.entities[0].name == "Profile"
    assert spec.apis[0].name == "GetProfile"
    assert spec.apis[0].output_entity == "Profile"


# ---------------------------------------------------------------------------
# Test 6: Empty arrays and empty objects
# ---------------------------------------------------------------------------
def test_6():
    src = """
resource "lattice_workflow" "no_steps" {
  name  = "NoSteps"
  steps = []
}
resource "lattice_entity" "bare" {
  name   = "Bare"
  fields = {}
}
"""
    spec = parse_string(src)
    assert len(spec.workflows) == 1
    assert spec.workflows[0].name == "NoSteps"
    assert spec.workflows[0].steps == [], f"Expected [], got {spec.workflows[0].steps}"
    assert len(spec.entities) == 1
    assert spec.entities[0].name == "Bare"
    assert spec.entities[0].fields == [], f"Expected [], got {spec.entities[0].fields}"


# ---------------------------------------------------------------------------
# Test 7: Int and float number parsing
# ---------------------------------------------------------------------------
def test_7():
    """See test_3 docstring: numeric array values exercised via publishes, not steps."""
    src = """
resource "lattice_api" "num_test" {
  name      = "NumTest"
  method    = "POST"
  path      = "/num-test"
  publishes = [3.14, 2.718, 1.0, 100, 0, 999999]
}
"""
    spec = parse_string(src)
    steps = spec.apis[0].publishes
    assert steps[0] == 3.14
    assert isinstance(steps[0], float), f"Expected float, got {type(steps[0]).__name__}"
    assert steps[1] == 2.718
    assert isinstance(steps[1], float), f"Expected float, got {type(steps[1]).__name__}"
    assert steps[2] == 1.0
    assert isinstance(steps[2], float), f"Expected float, got {type(steps[2]).__name__}"
    assert steps[3] == 100
    assert isinstance(steps[3], int), f"Expected int, got {type(steps[3]).__name__}"
    assert steps[4] == 0
    assert isinstance(steps[4], int), f"Expected int, got {type(steps[4]).__name__}"
    assert steps[5] == 999999
    assert isinstance(steps[5], int), f"Expected int, got {type(steps[5]).__name__}"
    print(f"        Number types: {[type(x).__name__ for x in steps]}")


# ---------------------------------------------------------------------------
# Test 8: FastAPI output (schemas + routes + app) compiles
# ---------------------------------------------------------------------------
def test_8():
    src = """
resource "lattice_entity" "author" {
  name = "Author"
  fields = {
    id       = "uuid"
    username = "string"
    email    = "string"
    bio      = "string"
  }
}
resource "lattice_entity" "post" {
  name = "Post"
  fields = {
    id           = "uuid"
    author_id    = "uuid"
    title        = "string"
    content      = "string"
    status       = "string"
    published_at = "datetime"
  }
}
resource "lattice_api" "create_post" {
  name   = "CreatePost"
  method = "POST"
  path   = "/posts"
  input  = lattice_entity.post.name
  output = lattice_entity.post.name
}
resource "lattice_api" "get_post" {
  name   = "GetPost"
  method = "GET"
  path   = "/posts/{id}"
  output = lattice_entity.post.name
}
resource "lattice_api" "list_posts" {
  name   = "ListPosts"
  method = "GET"
  path   = "/posts"
  output = lattice_entity.post.name
}
"""
    spec = parse_string(src)
    for label, gen_fn in (
        ("schemas", schemas_generate),
        ("routes", routes_generate),
        ("app", app_generate),
    ):
        code = gen_fn(spec)
        try:
            ast.parse(code)
            print(f"        FastAPI {label} generated {len(code)} bytes, AST is valid")
        except SyntaxError:
            print(f"        SyntaxError in generated {label} code (first 500 chars):")
            print(f"        {code[:500]}")
            raise


# ---------------------------------------------------------------------------
# Test 9: SQLAlchemy output compiles
# ---------------------------------------------------------------------------
def test_9():
    src = """
resource "lattice_entity" "user" {
  name = "User"
  fields = {
    id    = "uuid"
    email = "string"
    name  = "string"
  }
}
resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id         = "uuid"
    user_id    = "uuid"
    total      = "float"
    status     = "string"
    created_at = "datetime"
  }
}
resource "lattice_entity" "product" {
  name = "Product"
  fields = {
    id    = "uuid"
    name  = "string"
    price = "float"
    stock = "int"
  }
}
"""
    spec = parse_string(src)
    code = sqlalchemy_generate(spec)
    try:
        ast.parse(code)
        print(f"        SQLAlchemy generated {len(code)} bytes, AST is valid")
    except SyntaxError:
        print("        SyntaxError in generated code (first 500 chars):")
        print(f"        {code[:500]}")
        raise


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Parser Edge Case Tests")
    print("=" * 50)

    tests = [
        (1, "All 5 resource types", test_1),
        (2, "Comments, blank lines, indentation", test_2),
        (3, "Arrays with mixed types (strings, numbers)", test_3),
        (4, "Nested object values", test_4),
        (5, "Forward references (entity after API)", test_5),
        (6, "Empty arrays and empty objects", test_6),
        (7, "Int and float number parsing", test_7),
        (8, "FastAPI generated code (schemas/routes/app) is compilable (ast.parse)", test_8),
        (9, "SQLAlchemy generated code is compilable (ast.parse)", test_9),
    ]

    for num, name, fn in tests:
        run_test(num, name, fn)

    print(f"\n{'=' * 50}")
    passed = sum(1 for _, _, r in results if r == "PASS")
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    for num, name, result in results:
        status = "PASS" if result == "PASS" else "FAIL"
        print(f"  [{status}] Test {num}: {name}")

    if passed != total:
        sys.exit(1)
