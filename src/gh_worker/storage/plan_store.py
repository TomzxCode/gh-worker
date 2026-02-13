"""Plan storage management."""

from datetime import UTC, datetime
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
        commit_hash: str | None = None,
    ) -> PlanMetadata:
        """Create a new plan for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number
            content: Plan content in markdown
            agent: Name of agent used to generate the plan
            model: Model used by the agent
            commit_hash: Repository commit hash when plan was generated

        Returns:
            PlanMetadata object
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        issue_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC)
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
            commit_hash=commit_hash,
        )

        # Save metadata
        metadata_file = plan_file.with_suffix(".yaml")
        metadata.save(metadata_file)

        return metadata

    def start_plan_generation(
        self, repository: Repository, issue_number: int
    ) -> tuple[Path, PlanMetadata]:
        """Create plan metadata at start of generation. Call complete_plan when done.

        Creates metadata only (no .md yet). If metadata exists but .md doesn't,
        plan is being generated (or failed).

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Tuple of (plan_file, metadata) - plan_file is the .md path to create in complete_plan
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        issue_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC)
        plan_filename = f"plan-{timestamp.strftime('%Y%m%d-%H%M%S')}.md"
        plan_file = issue_dir / plan_filename

        metadata = PlanMetadata(
            issue_number=issue_number,
            repository=repository.full_name,
            created_at=timestamp,
            plan_file=plan_file,
        )
        metadata.save(plan_file.with_suffix(".yaml"))
        return (plan_file, metadata)

    def complete_plan(
        self,
        plan_file: Path,
        metadata: PlanMetadata,
        content: str,
        *,
        agent: str | None = None,
        model: str | None = None,
        commit_hash: str | None = None,
        session_id: str | None = None,
    ) -> PlanMetadata:
        """Complete plan generation: write content and update metadata.

        Args:
            plan_file: Plan file path (from start_plan_generation)
            metadata: Metadata from start_plan_generation
            content: Plan content
            agent: Agent name
            model: Model name
            commit_hash: Repository commit hash
            session_id: Session ID (if not already set via callback during generation)

        Returns:
            Updated metadata
        """
        plan_file.write_text(content)
        metadata.agent = agent
        metadata.model = model
        metadata.commit_hash = commit_hash
        if session_id is not None:
            metadata.session_id = session_id
        metadata.save(plan_file.with_suffix(".yaml"))
        return metadata

    def get_latest_plan(
        self, repository: Repository, issue_number: int
    ) -> tuple[Path, PlanMetadata] | None:
        """Get the latest plan for an issue.

        Returns metadata even if .md doesn't exist yet (plan being generated).
        plan_file may not exist - callers should check plan_file.exists() for complete plans.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Tuple of (plan_file, metadata) or None if no plan metadata exists
        """
        issue_dir = self.get_issue_dir(repository, issue_number)

        if not issue_dir.exists():
            return None

        # Find all plan metadata files (source of truth - created first during generation)
        metadata_files = sorted(issue_dir.glob("plan-*.yaml"), reverse=True)

        if not metadata_files:
            return None

        metadata = PlanMetadata.load(metadata_files[0])
        plan_file = metadata_files[0].with_suffix(".md")
        metadata.plan_file = plan_file

        return (plan_file, metadata)

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
                    created_at=datetime.fromtimestamp(plan_file.stat().st_mtime, tz=UTC),
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
                updated_at = updated_at.replace(tzinfo=UTC)
            else:
                updated_at = updated_at.astimezone(UTC)
        except (ValueError, OSError):
            return False

        # Check if there's a plan matching this timestamp
        # A plan matches if it was created at or after the updated-at timestamp
        plans = self.list_plans(repository, issue_number)
        for _plan_file, metadata in plans:
            # Normalize plan created_at to UTC-aware datetime for comparison
            plan_created_at = metadata.created_at
            if plan_created_at.tzinfo is None:
                plan_created_at = plan_created_at.replace(tzinfo=UTC)
            else:
                plan_created_at = plan_created_at.astimezone(UTC)

            # Plan matches if created_at is at or after the updated_at timestamp
            if plan_created_at >= updated_at:
                return True

        return False
