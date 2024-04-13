import pytest 
from server import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_register_user_success(client):
    data = {
        "firstName": "John",
        "lastName": "Doe",
        "email": "john.doe@example.com",
        "password": "TestPassword123",
        "confirmPassword": "TestPassword123",
        "occupation": "Engineer"
    }
    response = client.post('/register', json=data)
    assert response.status_code == 201
    assert 'id' in response.json
    assert response.json['email'] == data['email']

def test_register_user_missing_name(client):
    data = {
        "email": "john.doe@example.com",
        "password": "TestPassword123",
        "confirmPassword": "TestPassword123",
        "occupation": "Engineer"
    }
    response = client.post('/register', json=data)
    assert response.status_code == 400
    assert 'error' in response.json
    assert 'First name and last name are required' in response.json['error']