"""
Vendor credentials configuration — HP OneView, Dell OME, Cisco UCS.
"""

import os


class VendorConfig:
    """Vendor-specific credentials and connection settings."""

    # HP OneView
    ONEVIEW_IP = os.getenv("ONEVIEW_IP")
    ONEVIEW_USERNAME = os.getenv("ONEVIEW_USERNAME")
    ONEVIEW_PASSWORD = os.getenv("ONEVIEW_PASSWORD")

    # Dell OpenManage Enterprise
    OME_IP = os.getenv("OME_IP")
    OME_USERNAME = os.getenv("OME_USERNAME")
    OME_PASSWORD = os.getenv("OME_PASSWORD")

    # Cisco UCS Central
    UCS_CENTRAL_IP = os.getenv("UCS_CENTRAL_IP")
    UCS_CENTRAL_USERNAME = os.getenv("UCS_CENTRAL_USERNAME")
    UCS_CENTRAL_PASSWORD = os.getenv("UCS_CENTRAL_PASSWORD")

    # Cisco UCS Manager (per-domain connections)
    UCS_MANAGER_USERNAME = os.getenv("UCS_MANAGER_USERNAME")
    UCS_MANAGER_PASSWORD = os.getenv("UCS_MANAGER_PASSWORD")

    @classmethod
    def get_credentials(cls, vendor: str) -> dict:
        """Return the credentials dict for a given vendor name."""
        vendor_upper = vendor.upper()
        if vendor_upper == "HP":
            return {
                "ip": cls.ONEVIEW_IP,
                "username": cls.ONEVIEW_USERNAME,
                "password": cls.ONEVIEW_PASSWORD,
            }
        elif vendor_upper == "DELL":
            return {
                "ip": cls.OME_IP,
                "username": cls.OME_USERNAME,
                "password": cls.OME_PASSWORD,
            }
        elif vendor_upper == "CISCO":
            return {
                "central_ip": cls.UCS_CENTRAL_IP,
                "central_username": cls.UCS_CENTRAL_USERNAME,
                "central_password": cls.UCS_CENTRAL_PASSWORD,
                "manager_username": cls.UCS_MANAGER_USERNAME,
                "manager_password": cls.UCS_MANAGER_PASSWORD,
            }
        else:
            raise ValueError(f"Unknown vendor: {vendor}")
