from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password):
    return generate_password_hash(password)

def check_password(hash_pw, password):
    return check_password_hash(hash_pw, password)
