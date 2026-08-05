from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import TimestampMixin


class Installation(Base, TimestampMixin):
    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_installation_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    suspended: Mapped[bool] = mapped_column(default=False, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="installations")
