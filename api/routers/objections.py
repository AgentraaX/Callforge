"""Objection playbook CRUD endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/objections", tags=["objections"])
