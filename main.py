"""
Student Management API Backend
FastAPI with Supabase PostgreSQL Database
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

# ============================================
# CONFIGURATION
# ============================================

app = FastAPI(
    title=os.getenv("API_TITLE", "Student Management API"),
    version=os.getenv("API_VERSION", "1.0.0"),
    description="API for managing student records",
    contact={"name": "Your Name"}
)

# Enable CORS (allow frontend to access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_URL = os.getenv("DB_URL")

# ============================================
# PYDANTIC MODELS (Data Validation)
# ============================================

class StudentBase(BaseModel):
    """Base student model - shared fields"""
    student_id: str = Field(..., min_length=1, max_length=20, 
description="Unique student ID")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    major: Optional[str] = Field(None, max_length=100)
    gpa: Optional[float] = Field(default=0.0, ge=0.0, le=4.0)
    status: str = Field(default="active", description="active, inactive, graduated")
    phone: Optional[str] = Field(None, max_length=15)

class StudentCreate(StudentBase):
    """Model for creating a student"""
    pass

class StudentUpdate(BaseModel):
    """Model for updating a student - all fields optional"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    major: Optional[str] = None
    gpa: Optional[float] = None
    status: Optional[str] = None
    phone: Optional[str] = None

class StudentResponse(StudentBase):
    """Model for returning student data"""
    id: int
    enrollment_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ============================================
# DATABASE HELPER FUNCTIONS
# ============================================

def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(DB_URL)
        return conn
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed"
        )

def dict_from_db(cursor):
    """Convert database cursor to list of dictionaries"""
    if cursor.description:
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    return []

# ============================================
# API ENDPOINTS
# ============================================

# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """Check if API is running"""
    return {
        "status": "healthy",
        "message": "Student API is running",
        "timestamp": datetime.now().isoformat()
    }

# ========== GET ALL STUDENTS ==========
@app.get(
    "/api/students",
    response_model=dict,
    tags=["Students"],
    summary="Get all students"
)
async def get_all_students(skip: int = 0, limit: int = 100):
    """
    Get all students from database
    
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT * FROM students ORDER BY id LIMIT %s OFFSET %s",
            (limit, skip)
        )
        students = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) AS total_count FROM students")
        total = cursor.fetchone()["total_count"]
        
        cursor.close()
        conn.close()
        
        return {
            "data": [dict(student) for student in students],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching students: {str(e)}"
        )

# ========== GET SINGLE STUDENT ==========
@app.get(
    "/api/students/{student_id}",
    response_model=dict,
    tags=["Students"],
    summary="Get specific student"
)
async def get_student(student_id: int):
    """
    Get a specific student by ID
    
    - **student_id**: The database ID of the student
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT * FROM students WHERE id = %s", 
(student_id,))
        student = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {student_id} not found"
            )
        
        return dict(student)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ========== CREATE STUDENT ==========
@app.post(
    "/api/students",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    tags=["Students"],
    summary="Create new student"
)
async def create_student(student: StudentCreate):
    """
    Create a new student record
    
    - **student_id**: Unique student identifier (e.g., STU001)
    - **first_name**: First name (required)
    - **last_name**: Last name (required)
    - **email**: Email address (required, must be unique)
    - **major**: Field of study (optional)
    - **gpa**: Grade point average 0.0-4.0 (optional)
    - **status**: active/inactive/graduated (default: active)
    - **phone**: Phone number (optional)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if student_id already exists
        cursor.execute("SELECT id FROM students WHERE student_id = %s", 
(student.student_id,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student ID '{student.student_id}' already exists"
            )
        
        # Check if email already exists
        cursor.execute("SELECT id FROM students WHERE email = %s", 
(student.email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{student.email}' already exists"
            )
        
        # Insert new student
        cursor.execute("""
            INSERT INTO students 
            (student_id, first_name, last_name, email, major, gpa, status, 
phone)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            student.student_id,
            student.first_name,
            student.last_name,
            student.email,
            student.major,
            student.gpa,
            student.status,
            student.phone
        ))
        
        new_student = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": "Student created successfully",
            "data": dict(new_student)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating student: {str(e)}"
        )

# ========== UPDATE STUDENT ==========
@app.put(
    "/api/students/{student_id}",
    response_model=dict,
    tags=["Students"],
    summary="Update student"
)
async def update_student(student_id: int, student_update: StudentUpdate):
    """
    Update a student record
    
    Provide only the fields you want to update. Other fields will remain 
unchanged.
    
    - **student_id**: Database ID of the student to update
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", 
(student_id,))
        existing_student = cursor.fetchone()
        
        if not existing_student:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {student_id} not found"
            )
        
        # Build update query dynamically
        update_fields = []
        values = []
        
        if student_update.first_name is not None:
            update_fields.append("first_name = %s")
            values.append(student_update.first_name)
        
        if student_update.last_name is not None:
            update_fields.append("last_name = %s")
            values.append(student_update.last_name)
        
        if student_update.email is not None:
            # Check if email is unique
            cursor.execute("""
                SELECT id 
                FROM students 
                WHERE email = %s AND id != %s""", (student_update.email, student_id))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"""Email '{student_update.email}' already exists"""
                )
            update_fields.append("email = %s")
            values.append(student_update.email)
        
        if student_update.major is not None:
            update_fields.append("major = %s")
            values.append(student_update.major)
        
        if student_update.gpa is not None:
            update_fields.append("gpa = %s")
            values.append(student_update.gpa)
        
        if student_update.status is not None:
            update_fields.append("status = %s")
            values.append(student_update.status)
        
        if student_update.phone is not None:
            update_fields.append("phone = %s")
            values.append(student_update.phone)
        
        # If no fields to update
        if not update_fields:
            cursor.close()
            conn.close()
            return dict(existing_student)
        
        # Always update the updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(student_id)
        
        # Execute update
        query = f"""
           UPDATE students 
           SET {', '.join(update_fields)} 
           WHERE id = %s RETURNING *"""
        cursor.execute(query, values)
        
        updated_student = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": "Student updated successfully",
            "data": dict(updated_student)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating student: {str(e)}"
        )

# ========== DELETE STUDENT ==========
@app.delete(
    "/api/students/{student_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    tags=["Students"],
    summary="Delete student"
)
async def delete_student(student_id: int):
    """
    Delete a student record
    
    - **student_id**: Database ID of the student to delete
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", 
(student_id,))
        student = cursor.fetchone()
        
        if not student:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {student_id} not found"
            )
        
        # Delete student
        cursor.execute("DELETE FROM students WHERE id = %s", 
(student_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": "Student deleted successfully",
            "data": dict(student)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting student: {str(e)}"
        )

# ========== ROOT ENDPOINT ==========
@app.get("/")
async def root():
    """API root endpoint with links"""
    return {
        "message": "Student Management API",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/health",
        "endpoints": {
            "GET /api/students": "Get all students",
            "GET /api/students/{id}": "Get specific student",
            "POST /api/students": "Create new student",
            "PUT /api/students/{id}": "Update student",
            "DELETE /api/students/{id}": "Delete student"
        }
    }

# ============================================
# START APP
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
