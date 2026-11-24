"""Générer les pièces localement et lier leur rendu aux preuves R3."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from circuit import check_claims, current_context, digest, fingerprint, normalize, read_receipt, require, verify_letter


def file_hash(path):
    return digest(Path(path).read_bytes())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paragraph(text, style):
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def embedded_fonts(family):
    names = (family + "-Regular", family + "-Bold")
    if not all(name in pdfmetrics.getRegisteredFontNames() for name in names):
        configured = os.environ.get("CANDIDATURES_FONT_DIR")
        paths = [Path(configured)] if configured else [
            Path("/usr/share/fonts/truetype/liberation"),
            Path("/usr/share/fonts/truetype/liberation2"),
        ]
        directory = next((path for path in paths if all((path / (name + ".ttf")).is_file() for name in names)), None)
        require(directory is not None, "Installer les polices Liberation ou configurer CANDIDATURES_FONT_DIR")
        for name in names:
            pdfmetrics.registerFont(TTFont(name, str(directory / (name + ".ttf"))))
    return names


def render_and_check(story, path, expected, margin=23):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as directory:
        draft = Path(directory) / "piece.pdf"
        doc = SimpleDocTemplate(
            str(draft), pagesize=A4, topMargin=20 * mm, bottomMargin=19 * mm,
            leftMargin=margin * mm, rightMargin=margin * mm,
        )
        doc.build(story)
        reader = PdfReader(draft)
        require(len(reader.pages) == 1, "La pièce doit tenir sur un A4 lisible")
        text = subprocess.check_output(["pdftotext", "-enc", "UTF-8", str(draft), "-"], text=True)
        extracted = normalize(text)
        require(all(normalize(line) in extracted for line in expected), "Texte extrait incomplet ou différent")
        preview = draft.with_suffix(".png")
        subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "130", "-png", "-singlefile",
                        str(draft), str(preview.with_suffix(""))], check=True, capture_output=True)
        draft.replace(path)
        preview.replace(path.with_suffix(".png"))
    return path.with_suffix(".png")


def letter_story(letter):
    regular, bold = embedded_fonts("LiberationSerif")
    body = ParagraphStyle("Body", fontName=regular, fontSize=12, leading=16.5,
                          spaceAfter=10, alignment=TA_JUSTIFY)
    left = ParagraphStyle("Left", parent=body, alignment=TA_LEFT)
    right = ParagraphStyle("Right", parent=left, alignment=TA_RIGHT)
    strong = ParagraphStyle("Strong", parent=left, fontName=bold)
    header_left = paragraph("\n".join(letter["sender"]), left)
    header_right = paragraph("\n".join(letter["recipient"]), right)
    header = Table([[header_left, header_right]], colWidths=[80 * mm, 80 * mm],
                   style=[("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("LEFTPADDING", (0, 0), (-1, -1), 0),
                          ("RIGHTPADDING", (0, 0), (-1, -1), 0)])
    story = [header, Spacer(1, 12 * mm), paragraph(letter["subject"], strong)]
    if letter.get("reference_line"):
        story.append(paragraph(letter["reference_line"], left))
    story.extend([Spacer(1, 3 * mm), paragraph(letter["salutation"], left)])
    story.extend(paragraph(text, body) for text in letter["paragraphs"])
    story.extend([paragraph(letter["closing"], left), Spacer(1, 3 * mm), paragraph(letter["signature"], strong)])
    return story


def compose_letter(dossier, cv_path, pdf_path):
    context = current_context(dossier["offer"], dossier["route"], dossier["directives"], file_hash(cv_path))
    read_receipt(context, dossier["read"], dossier["facts"])
    letter = dossier["letter"]
    require(bool(letter.get("paragraphs")), "Le corps de la lettre est requis")
    check_claims(letter["paragraphs"], letter["claims"], dossier["facts"])
    body = [letter["salutation"], *letter["paragraphs"], letter["closing"], letter["signature"]]
    preview = render_and_check(letter_story(letter), pdf_path, [letter["subject"], *body])
    files = {"pdf": str(pdf_path), "render": str(preview), "text": str(Path(pdf_path).with_suffix(".txt"))}
    Path(files["text"]).write_text("\n\n".join([letter["subject"], *body]) + "\n", encoding="utf-8")
    if letter.get("portal_text"):
        portal = Path(pdf_path).with_name(Path(pdf_path).stem + "_portail.txt")
        portal.write_text(letter["portal_text"] + "\n", encoding="utf-8")
        files["portal_text"] = str(portal)
    return {
        "status": "GENERATED_UNQUALIFIED", "context": context, "files": files,
        "draft_sha256": fingerprint(letter),
        "hashes": {key: file_hash(path) for key, path in files.items()},
    }


def gate_letter(dossier, cv, generated, review):
    context = current_context(dossier["offer"], dossier["route"], dossier["directives"], file_hash(cv))
    read_receipt(context, dossier["read"], dossier["facts"])
    require(generated.get("draft_sha256") == fingerprint(dossier["letter"]), "Le projet de lettre a changé")
    observed = {key: file_hash(path) for key, path in generated["files"].items()}
    require({"pdf", "render", "text"} <= observed.keys(), "Pièces R3 obligatoires manquantes")
    return verify_letter(context, generated, review, observed)


def make_variant(source, profile, order, reference, output):
    cv_text = normalize(subprocess.check_output(["pdftotext", "-enc", "UTF-8", str(source), "-"], text=True))
    blocks = {block["id"]: block for block in profile["blocks"]}
    require(len(blocks) == len(profile["blocks"]) and set(order) == set(blocks) and len(order) == len(blocks),
            "Les mêmes blocs doivent figurer exactement une fois")
    expected = [*profile["header"], *(line for block in blocks.values() for line in block["lines"])]
    require(all(normalize(line) and normalize(line) in cv_text for line in expected),
            "Un fait du CV dérivé est absent du CV canonique")
    require(profile.get("fixed_facts") and all(
        any(normalize(fact) in normalize(line) for line in expected) for fact in profile["fixed_facts"]
    ),
            "Attester le maintien des faits fixes")
    regular, bold = embedded_fonts("LiberationSans")
    base = ParagraphStyle("CV body", fontName=regular, fontSize=9.5, leading=11.4, spaceAfter=1.6)
    headline = ParagraphStyle("CV title", parent=base, fontName=bold,
                              fontSize=17, leading=21, textColor=HexColor("#15364A"), spaceAfter=4)
    heading = ParagraphStyle("CV section", parent=base, fontName=bold,
                             fontSize=10.5, leading=12.5, textColor=HexColor("#15364A"), spaceBefore=5)
    story = [paragraph(profile["header"][0], headline)]
    story.extend(paragraph(text, base) for text in profile["header"][1:])
    for key in order:
        block = blocks[key]
        story.append(paragraph(block["label"], heading))
        story.extend(paragraph(line, base) for line in block["lines"])
    rendered = render_and_check(story, output, expected, margin=16)
    return {
        "status": "GENERATED_UNQUALIFIED", "reference": reference, "source_sha256": file_hash(source),
        "sha256": file_hash(output), "render_sha256": file_hash(rendered), "order": list(order),
    }


def qualify_variant(source, output, receipt, observation):
    require(receipt.get("source_sha256") == file_hash(source) and receipt.get("sha256") == file_hash(output),
            "Le CV ou son fichier source a changé")
    require(receipt.get("render_sha256") == file_hash(Path(output).with_suffix(".png")),
            "Le rendu du CV a changé")
    require(observation and observation.strip(), "Inspecter le rendu final du CV")
    return {**receipt, "status": "PASS", "render_observation": observation}
