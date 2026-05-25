from config.brand import b, fmt, brand


def test_brand_loads():
    data = brand()
    assert isinstance(data, dict)
    assert "studio" in data


def test_b_accessor():
    assert b("studio.name") == "AI Studio Accademia Milano"
    assert b("studio.founder_name") == "Luigi"
    assert b("github.full_repo") == "laceto/AIstudioAccademiaMilano"


def test_fmt_placeholder():
    result = fmt("Welcome to {studio.name}!")
    assert result == "Welcome to AI Studio Accademia Milano!"


def test_fmt_nested():
    result = fmt("{studio.founder_name} is the founder of {studio.name}.")
    assert result == "Luigi is the founder of AI Studio Accademia Milano."
