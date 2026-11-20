"""Read-only JSON-lines interface to shacl-py's DataLad and catalogue readers."""

import json
import sys
import uuid
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import yaml
from shacl_py.branding import branding
from shacl_py.browser import (
    dataset_keys, file_metadata, file_selection, items_from, neighbours,
    publication_key, source_content,
)
from shacl_py.files import scoped_path
from shacl_py.native import declared_title
from shacl_py.records import load_records
from shacl_py.sources import source_url
from shacl_py.study import person_names


def text(value):
    if isinstance(value, list):
        return ", ".join(filter(None, map(text, value)))
    if isinstance(value, dict):
        return declared_title(value) or str(value.get("@id", ""))
    return "" if value is None else str(value)


def field(item, *keys):
    return next((text(item.fields[key]) for key in keys if item.fields.get(key)), "")


def author(item, primary=False):
    data = source_content(item.source)
    ids = item.fields.get("author")
    people = data.get("person", {}) if isinstance(data, dict) else {}
    first = field(item, "primary_author") if primary else ""
    if first:
        return person_names(people, [first])[0]
    if people and isinstance(ids, list) and all(isinstance(key, str) for key in ids):
        return ", ".join(person_names(people, ids))
    return field(item, "author_names", "authors", "author", "creator")


def record_id(item):
    return json.dumps([item.ref, item.key], separators=(",", ":"), ensure_ascii=False)


def as_yaml(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


class Project:
    def __init__(self, path):
        self.root = Path(path).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Choose a project folder.")
        self.token = uuid.uuid4().hex
        records, self.warnings = load_records(self.root)
        items = list(items_from(records, self.root))
        self.stored_files = file_metadata(records)
        papers = [i for i in items if i.is_publication]
        datasets = [i for i in items if i.is_dataset]
        dataset_ids = dataset_keys(papers, datasets)
        self.groups = defaultdict(list)
        self.ids = {}
        representatives = {}
        # Prefer the authored catalogue when native sources describe the same entity.
        for item in sorted(items, key=lambda i: not hasattr(i.source, "graph")):
            key = dataset_ids[item] if item.is_dataset else publication_key(item)
            uid = representatives.setdefault(key, record_id(item))
            self.groups[uid].append(item)
            self.ids[item] = uid
        self.links = {uid: {} for uid in self.groups}
        for item in items:
            own = self.ids[item]
            for other, role in neighbours(item, items).items():
                target = self.ids[other]
                if own != target:
                    self.links[own].setdefault(target, role)
        self.listing = lru_cache(maxsize=64)(self._listing)
        self.search_index = {}

    def describe(self, uid, group):
        item = group[0]
        labels = item.fields.get("labels") or []
        reviews = getattr(item.source, "graph", {}).get("reviews", [])
        raw_url = field(item, "doi", "source_url", "url", "sameAs")
        url = ""
        if raw_url:
            try:
                url = source_url(raw_url)
            except ValueError:
                pass
        return {
            "id": uid, "title": str(item.label), "kind": item.kind,
            "section": "Datasets" if item.is_dataset else "Papers" if item.is_publication else "Records",
            "pid": field(item, "pid", "@id", "identifier"),
            "folder": item.folder.relative_to(self.root).as_posix() if item.has_folder else "",
            "authors": author(item), "primaryAuthor": author(item, primary=True),
            "venue": field(item, "venue", "journal", "isPartOf"),
            "year": field(item, "year", "datePublished"),
            "abstract": field(item, "abstract", "description"),
            "notes": "\n\n".join(filter(None, [field(item, "notes"), *(
                text(r.get("notes")) for r in reviews if r.get("publication") == item.key
            )])),
            "format": field(item, "format", "encodingFormat", "media_type"),
            "labels": [str(v) for v in (labels if isinstance(labels, list) else [labels])],
            "keywords": field(item, "keywords", "keyword"),
            "url": url, "urlLabel": raw_url, "links": self.links[uid],
        }

    def overview(self):
        brand = branding(self.root)
        if brand["app_name"] == "shaclpy" and not (self.root / ".shacl-py/config.yaml").is_file():
            brand["app_name"] = "DS View"
        return {"session": self.token, "name": self.root.name, "root": str(self.root),
                "brand": brand, "warnings": self.warnings,
                "records": [self.describe(uid, group) for uid, group in self.groups.items()]}

    def _listing(self, uid, directory):
        item = self.groups[uid][0]
        folders, groups = file_selection(item, directory)
        rows = {r["Relative path"]: r for _, members in groups for r in members}
        if item.is_publication:
            for linked in self.links[uid]:
                dataset = self.groups[linked][0]
                if dataset.is_dataset:
                    _, members = self.listing(linked, ".")
                    for name in members:
                        try:
                            relative = (dataset.folder / name).relative_to(item.folder).as_posix()
                        except ValueError:
                            continue
                        rows.pop(relative, None)
        return folders, rows

    def files(self, uid, folder):
        item = self.groups[uid][0]
        directories, members = self.listing(uid, folder)
        rows = []
        for name, row in members.items():
            local = row["Availability"] == "Available"
            size = None
            if local:
                try:
                    size = scoped_path(item.folder, name).stat().st_size
                except OSError:
                    pass
            rows.append({"path": name, "local": local, "size": size})
        return {"folders": directories, "rows": rows}

    def file(self, uid, folder, name, preview):
        item = self.groups[uid][0]
        _, rows = self.listing(uid, folder)
        if name not in rows:
            raise ValueError("This file is outside the selected record.")
        path = scoped_path(item.folder, name)
        result = {"metadata": self.stored_files.get(path, []), "preview": None,
                  "truncated": False, "canPreview": rows[name]["Availability"] == "Available"
                  and not path.is_symlink() and path.is_file()}
        if preview and result["canPreview"]:
            with path.open("rb") as stream:
                data = stream.read(8193)
            try:
                from codecs import getincrementaldecoder
                if b"\x00" in data:
                    raise ValueError("binary")
                result["preview"] = getincrementaldecoder("utf-8")().decode(data[:8192], final=len(data) <= 8192)
                result["truncated"] = len(data) > 8192
            except ValueError:
                result["canPreview"] = False
        return result

    def query(self, message):
        if message["session"] != self.token:
            raise ValueError("The selected project has changed.")
        if message["op"] == "search":
            term = message["term"].casefold()
            matched = set()
            for uid, group in self.groups.items():
                if uid not in self.search_index:
                    item = group[0]
                    _, files = self.listing(uid, ".")
                    self.search_index[uid] = "\n".join([
                        json.dumps(item.fields, ensure_ascii=False, default=str),
                        *files, *(json.dumps(self.stored_files[item.folder / path], ensure_ascii=False, default=str)
                                 for path in files if item.folder / path in self.stored_files),
                    ]).casefold()
                if term in self.search_index[uid]:
                    matched.add(uid)
            return list(matched | {uid for uid, links in self.links.items()
                                   if any(k in matched and self.groups[k][0].is_dataset for k in links)})
        uid = message["id"]
        if uid not in self.groups:
            raise ValueError("Unknown metadata record.")
        if message["op"] == "source":
            return [{"name": i.ref, "fields": as_yaml(i.fields), "source": as_yaml(source_content(i.source))}
                    for i in self.groups[uid]]
        if message["op"] == "files":
            return self.files(uid, message["folder"])
        if message["op"] == "file":
            return self.file(uid, message["folder"], message["path"], message.get("preview", False))
        raise ValueError("Unknown reader operation.")


def serve():
    project = None
    sys.stdin.reconfigure(encoding="utf-8")
    # Keep third-party progress output off the JSON protocol.
    protocol = sys.stdout
    sys.stdout = sys.stderr
    for line in sys.stdin:
        try:
            message = json.loads(line)
            op = message["op"]
            if op == "quit":
                return
            if op == "open" or op == "refresh":
                if op == "refresh" and (project is None or message["session"] != project.token):
                    raise ValueError("The selected project has changed.")
                new = Project(message["root"] if op == "open" else project.root)
                value = new.overview()
                project = new
            elif project is None:
                raise ValueError("Open a project folder first.")
            else:
                value = project.query(message)
            reply = {"value": value}
        except Exception as error:
            reply = {"error": str(error) or type(error).__name__}
        print(json.dumps(reply, ensure_ascii=True, default=str), file=protocol, flush=True)


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    serve()
