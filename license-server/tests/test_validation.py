from app.schemas import Login


def test_password_preserves_intentional_whitespace():
    assert Login(email="admin@example.com", password="  password with spaces  ").password == "  password with spaces  "
