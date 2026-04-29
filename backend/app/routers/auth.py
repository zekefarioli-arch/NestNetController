from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..models import LoginRequest, Token
from ..services import authenticate_user, create_access_token, verify_token

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    if not authenticate_user(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    access_token = create_access_token(data={"sub": request.username})
    return Token(access_token=access_token, token_type="bearer")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to verify JWT token and get current user"""
    payload = verify_token(credentials.credentials)
    return payload.get("sub")
