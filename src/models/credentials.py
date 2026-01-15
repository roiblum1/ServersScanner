"""
Pydantic models for vendor credentials with validation.

Provides type-safe configuration with automatic environment variable loading
and validation for all vendor APIs.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
import re
import os


class HPCredentials(BaseModel):
    """HP OneView credentials with validation"""
    ip: str = Field(..., description="OneView IP address or hostname")
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

    @validator('ip')
    def validate_ip(cls, v):
        """Basic hostname/IP validation"""
        if not re.match(r'^[\d\w\-\.]+$', v):
            raise ValueError('Invalid IP address or hostname format')
        return v

    class Config:
        frozen = True  # Immutable


class DellCredentials(BaseModel):
    """Dell OME credentials with validation"""
    ip: str = Field(..., description="OME IP address or hostname")
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

    @validator('ip')
    def validate_ip(cls, v):
        """Basic hostname/IP validation"""
        if not re.match(r'^[\d\w\-\.]+$', v):
            raise ValueError('Invalid IP address or hostname format')
        return v

    class Config:
        frozen = True  # Immutable


class CiscoCredentials(BaseModel):
    """Cisco UCS Central credentials with validation"""
    central_ip: str = Field(..., description="UCS Central IP address")
    central_username: str = Field(..., min_length=1)
    central_password: str = Field(..., min_length=1)
    manager_username: str = Field(..., min_length=1)
    manager_password: str = Field(..., min_length=1)

    @validator('central_ip')
    def validate_ip(cls, v):
        """Basic hostname/IP validation"""
        if not re.match(r'^[\d\w\-\.]+$', v):
            raise ValueError('Invalid IP address or hostname format')
        return v

    class Config:
        frozen = True  # Immutable


class VendorCredentialsConfig(BaseModel):
    """
    Unified vendor credentials configuration.

    Validates that at least one vendor is configured.
    """
    hp: Optional[HPCredentials] = None
    dell: Optional[DellCredentials] = None
    cisco: Optional[CiscoCredentials] = None

    @validator('cisco')
    def at_least_one_vendor(cls, v, values):
        """Ensure at least one vendor is configured"""
        if not any([values.get('hp'), values.get('dell'), v]):
            raise ValueError("At least one vendor must be configured")
        return v

    class Config:
        frozen = True  # Immutable

    @classmethod
    def from_env(cls) -> "VendorCredentialsConfig":
        """
        Load credentials from environment variables.

        Expected environment variables:
        - ONEVIEW_IP, ONEVIEW_USERNAME, ONEVIEW_PASSWORD
        - OME_IP, OME_USERNAME, OME_PASSWORD
        - UCS_CENTRAL_IP, UCS_CENTRAL_USERNAME, UCS_CENTRAL_PASSWORD,
          UCS_MANAGER_USERNAME, UCS_MANAGER_PASSWORD

        Returns:
            VendorCredentialsConfig with validated credentials

        Raises:
            ValueError: If no vendors are configured or validation fails
        """
        hp_creds = None
        if all([os.getenv("ONEVIEW_IP"), os.getenv("ONEVIEW_USERNAME"), os.getenv("ONEVIEW_PASSWORD")]):
            hp_creds = HPCredentials(
                ip=os.getenv("ONEVIEW_IP"),
                username=os.getenv("ONEVIEW_USERNAME"),
                password=os.getenv("ONEVIEW_PASSWORD")
            )

        dell_creds = None
        if all([os.getenv("OME_IP"), os.getenv("OME_USERNAME"), os.getenv("OME_PASSWORD")]):
            dell_creds = DellCredentials(
                ip=os.getenv("OME_IP"),
                username=os.getenv("OME_USERNAME"),
                password=os.getenv("OME_PASSWORD")
            )

        cisco_creds = None
        if all([
            os.getenv("UCS_CENTRAL_IP"),
            os.getenv("UCS_CENTRAL_USERNAME"),
            os.getenv("UCS_CENTRAL_PASSWORD"),
            os.getenv("UCS_MANAGER_USERNAME"),
            os.getenv("UCS_MANAGER_PASSWORD")
        ]):
            cisco_creds = CiscoCredentials(
                central_ip=os.getenv("UCS_CENTRAL_IP"),
                central_username=os.getenv("UCS_CENTRAL_USERNAME"),
                central_password=os.getenv("UCS_CENTRAL_PASSWORD"),
                manager_username=os.getenv("UCS_MANAGER_USERNAME"),
                manager_password=os.getenv("UCS_MANAGER_PASSWORD")
            )

        return cls(hp=hp_creds, dell=dell_creds, cisco=cisco_creds)

    def to_legacy_format(self) -> dict:
        """
        Convert to legacy dictionary format for backward compatibility.

        Returns:
            Dictionary matching old config structure
        """
        config = {}

        if self.hp:
            config["hp"] = {
                "ip": self.hp.ip,
                "username": self.hp.username,
                "password": self.hp.password
            }

        if self.dell:
            config["dell"] = {
                "ip": self.dell.ip,
                "username": self.dell.username,
                "password": self.dell.password
            }

        if self.cisco:
            config["cisco"] = {
                "central_ip": self.cisco.central_ip,
                "central_username": self.cisco.central_username,
                "central_password": self.cisco.central_password,
                "manager_username": self.cisco.manager_username,
                "manager_password": self.cisco.manager_password
            }

        return config
