"""Plan storage management."""

from datetime import datetime, timezone
from pathlib import Path

from gh_worker.models.plan import PlanMetadata
from gh_worker.models.repository import Repository


class PlanStore:
    """Manages file-based storage for implementation plans."""

    def __init__(self, issues_path: Path):
        """Initialize plan store.

        Args:
            issues_path: Base path for storing issues and plans
        """
        self.issues_path = Path(issues_path)

    def get_issue_dir(self, repository: Repository, issue_number: int) -> Path:
        """Get directory path for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Path to issue directory
        """
        return self.issues_path / repository.owner / repository.name / str(issue_number)

    def create_plan(
        self,
        repository: Repository,
        issue_number: int,
        content: str,
        *,
        agent: str | None = None,
        model: str | None = None,
    ) -> PlanMetadata:
        """Create a new plan for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number
            content: Plan content in markdown
            agent: Name of agent used to generate the plan
            model: Model used by the agent

        Returns:
            PlanMetadata object
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        issue_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc)
        plan_filename = f"plan-{timestamp.strftime('%Y%m%d-%H%M%S')}.md"
        plan_file = issue_dir / plan_filename

        # Save plan content
        plan_file.write_text(content)

        # Create metadata
        metadata = PlanMetadata(
            issue_number=issue_number,
            repository=repository.full_name,
            created_at=timestamp,
            plan_file=plan_file,
            agent=agent,
            model=model,
        )

        # Save metadata
        metadata_file = plan_file.with_suffix(".yaml")
        metadata.save(metadata_file)

        return metadata

    def get_latest_plan(
        self, repository: Repository, issue_number: int
    ) -> tuple[Path, PlanMetadata] | None:
        """Get the latest plan for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Tuple of (plan_file, metadata) or None if no plan exists
        """
        issue_dir = self.get_issue_dir(repository, issue_number)

        if not issue_dir.exists():
            return None

        # Find all plan files
        plan_files = sorted(issue_dir.glob("plan-*.md"), reverse=True)

        if not plan_files:
            return None

        # Get the latest plan
        latest_plan = plan_files[0]
        metadata_file = latest_plan.with_suffix(".yaml")

        if not metadata_file.exists():
            # Create default metadata if it doesn't exist
            metadata = PlanMetadata(
                issue_number=issue_number,
                repository=repository.full_name,
                created_at=datetime.fromtimestamp(latest_plan.stat().st_mtime, tz=timezone.utc),
                plan_file=latest_plan,
            )
        else:
            metadata = PlanMetadata.load(metadata_file)
            metadata.plan_file = latest_plan

        return (latest_plan, metadata)

    def list_plans(
        self, repository: Repository, issue_number: int
    ) -> list[tuple[Path, PlanMetadata]]:
        """List all plans for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            List of tuples (plan_file, metadata), sorted by creation time (newest first)
        """
        issue_dir = self.get_issue_dir(repository, issue_number)

        if not issue_dir.exists():
            return []

        plans = []
        plan_files = sorted(issue_dir.glob("plan-*.md"), reverse=True)

        for plan_file in plan_files:
            metadata_file = plan_file.with_suffix(".yaml")

            if metadata_file.exists():
                metadata = PlanMetadata.load(metadata_file)
                metadata.plan_file = plan_file
            else:
                # Create default metadata
                metadata = PlanMetadata(
                    issue_number=issue_number,
                    repository=repository.full_name,
                    created_at=datetime.fromtimestamp(plan_file.stat().st_mtime, tz=timezone.utc),
                    plan_file=plan_file,
                )

            plans.append((plan_file, metadata))

        return plans

    def update_metadata(self, metadata: PlanMetadata) -> None:
        """Update plan metadata.

        Args:
            metadata: PlanMetadata to update
        """
        if not metadata.plan_file:
            raise ValueError("PlanMetadata must have plan_file set")

        metadata_file = metadata.plan_file.with_suffix(".yaml")
        metadata.save(metadata_file)

    def has_plan(self, repository: Repository, issue_number: int) -> bool:
        """Check if an issue has a plan matching its .updated-at timestamp.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            True if a plan exists that matches the issue's .updated-at timestamp
        """
        issue_dir = self.get_issue_dir(repository, issue_number)

        if not issue_dir.exists():
            return False

        # Check if .updated-at file exists
        updated_at_file = issue_dir / ".updated-at"
        if not updated_at_file.exists():
            return False

        # Read the updated-at timestamp
        try:
            timestamp_str = updated_at_file.read_text().strip()
            updated_at = datetime.fromisoformat(timestamp_str)
            # Normalize to UTC-aware datetime for comparison
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            else:
                updated_at = updated_at.astimezone(timezone.utc)
        except (ValueError, OSError):
            return False

        # Check if there's a plan matching this timestamp
        # A plan matches if it was created at or after the updated-at timestamp
        plans = self.list_plans(repository, issue_number)
        for plan_file, metadata in plans:
            # Normalize plan created_at to UTC-aware datetime for comparison
            plan_created_at = metadata.created_at
            if plan_created_at.tzinfo is None:
                plan_created_at = plan_created_at.replace(tzinfo=timezone.utc)
            else:
                plan_created_at = plan_created_at.astimezone(timezone.utc)

            # Plan matches if created_at is at or after the updated_at timestamp
            if plan_created_at >= updated_at:
                return True

        return False
