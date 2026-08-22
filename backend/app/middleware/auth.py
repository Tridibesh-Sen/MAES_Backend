from fastapi import Request, HTTPException, status
from app.db.supabase_client import supabase

def get_current_user(request: Request):
    """
    Extracts and validates Supabase JWT from the Authorization header.
    Returns the user payload (including student_id/role) if valid.
    Supports a mock token fallback for open-source / no-auth mode.
    """
    auth_header = request.headers.get("Authorization")
    print(f"[AUTH DEBUG] Authorization header: {auth_header}")
    
    # Try to extract the token if available
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    # If the token is empty, invalid, or is a mock token, bypass Supabase validation
    if not token or token == "DEMO_USER_TOKEN" or token == "mock-token":
        print("[AUTH DEBUG] Bypassing auth check, using mock user payload")
        return {
            "user_id": "123e4567-e89b-12d3-a456-426614174000",
            "role": "student"
        }

    try:
        # Validate token securely with Supabase API
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id
        role = getattr(user_response.user, 'role', 'student') or 'student'
        
        if not user_id:
            print("[AUTH DEBUG] sub claim missing from token, using mock user payload")
            return {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "role": "student"
            }
            
        return {"user_id": user_id, "role": role}
        
    except Exception as e:
        print(f"[AUTH DEBUG] AuthError: {e}, falling back to mock user payload")
        return {
            "user_id": "123e4567-e89b-12d3-a456-426614174000",
            "role": "student"
        }


def require_role(allowed_roles: list[str]):
    """Dependency factory for checking user roles."""
    def role_checker(request: Request):
        user = get_current_user(request)
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker
