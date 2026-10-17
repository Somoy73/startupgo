"""Output serializers for scraper results."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Sequence

from .models import StartupLead


class LeadOutputWriter:
    """Serialize leads to stdout or a file in a selected format."""

    def write(
        self,
        leads: Sequence[StartupLead],
        *,
        output: Path | None,
        output_format: str,
    ) -> None:
        rendered = self.render(leads, output_format)
        if output:
            output.write_text(rendered + ("" if rendered.endswith("\n") else "\n"), encoding="utf-8")
        else:
            print(rendered)

    def render(self, leads: Sequence[StartupLead], output_format: str) -> str:
        rows = [asdict(lead) for lead in leads]
        if output_format == "json":
            return json.dumps(rows, indent=2, ensure_ascii=False)
        if output_format != "csv":
            raise ValueError(f"unsupported output format: {output_format}")
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=[field.name for field in fields(StartupLead)])
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()
