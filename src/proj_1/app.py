from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
import serial
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = ROOT / "data" / "images"
INDEX_PATH = ROOT / "data" / "index.json"
DEFAULT_MODEL = "qualcomm/Gemma-4-E4B-it:W4A16"
DEFAULT_SERVER = "http://127.0.0.1:18181"
SUPPORTED_TYPES = ["jpg", "jpeg", "png", "webp"]
SEARCH_STOP_WORDS = {"a", "an", "and", "are", "about", "does", "how", "image", "in", "is", "it", "me", "of", "please", "tell", "the", "this", "what", "where", "which", "who", "why"}
VISION_FAILURE_PHRASES = ("cannot see the image", "can't see the image", "provide the image", "unable to view the image")
CONTROLLER_BAUD_RATE = 115200


@st.cache_resource
def open_controller(port: str) -> serial.Serial:
    return serial.Serial(port, CONTROLLER_BAUD_RATE, timeout=0)


def controller_command(port: str, command: str) -> bool:
    if not port:
        return False
    try:
        connection = open_controller(port)
        connection.write((json.dumps({"command": command}) + "\n").encode("ascii"))
        connection.flush()
        return True
    except serial.SerialException:
        open_controller.clear()
        return False


def read_controller_events(port: str) -> list[dict[str, Any]]:
    if not port:
        return []
    try:
        connection = open_controller(port)
        events: list[dict[str, Any]] = []
        while connection.in_waiting:
            line = connection.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events
    except serial.SerialException:
        open_controller.clear()
        return []


@st.fragment(run_every="500ms")
def poll_controller(port: str, record_count: int) -> None:
    if not port or not record_count:
        return
    events = read_controller_events(port)
    rerun_required = False
    for event in events:
        st.session_state.last_controller_event = event
        event_name = event.get("event")
        if event_name == "knob":
            selected_index = int(event.get("value", 0)) % record_count
            if st.session_state.get("selected_image_index") != selected_index:
                st.session_state.selected_image_index = selected_index
                rerun_required = True
        elif event_name == "button" and event.get("value") == 0:
            st.session_state.hardware_submit = True
            rerun_required = True
        elif event_name == "button" and event.get("value") == 1:
            current_index = st.session_state.get("selected_image_index", 0)
            st.session_state.selected_image_index = (current_index + 1) % record_count
            rerun_required = True
    if rerun_required:
        st.rerun(scope="app")


def load_index() -> list[dict[str, str]]:
    if not INDEX_PATH.exists():
        return []
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_index(records: list[dict[str, str]]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def retrieval_score(question: str, record: dict[str, str]) -> int:
    question_words = tokenize(question) - SEARCH_STOP_WORDS
    explicit_words = tokenize(f"{record['name']} {record.get('note', '')}")
    description_words = tokenize(record.get("description", ""))
    score = 0
    for question_word in question_words:
        if any(
            question_word == searchable_word
            or (len(question_word) >= 3 and len(searchable_word) >= 3 and (question_word in searchable_word or searchable_word in question_word))
            for searchable_word in explicit_words
        ):
            score += 3
        elif any(
            question_word == searchable_word
            or (len(question_word) >= 3 and len(searchable_word) >= 3 and (question_word in searchable_word or searchable_word in question_word))
            for searchable_word in description_words
        ):
            score += 1
    return score


def retrieve_images(question: str, records: list[dict[str, str]], limit: int = 6) -> list[dict[str, str]]:
    ranked: list[tuple[int, int, dict[str, str]]] = []
    for position, record in enumerate(records):
        score = retrieval_score(question, record)
        ranked.append((score, position, record))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    matches = [item[2] for item in ranked if item[0] > 0]
    return (matches or [item[2] for item in ranked])[:limit]


def image_data_url(path: Path) -> str:
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower(), f"image/{path.suffix.lower().lstrip('.')}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def describe_image(server: str, model: str, record: dict[str, str]) -> str:
    path = ROOT / record["path"]
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the main subject and important visible details in this image in one short sentence for search."},
                {"type": "image_url", "image_url": {"url": image_data_url(path)}},
            ],
        }],
        "temperature": 0,
        "max_tokens": 80,
    }
    response = requests.post(f"{server.rstrip('/')}/v1/chat/completions", json=payload, timeout=180)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def enrich_records(server: str, model: str, records: list[dict[str, str]]) -> list[dict[str, str]]:
    changed = False
    for record in records:
        if record.get("description") or not (ROOT / record["path"]).exists():
            continue
        record["description"] = describe_image(server, model, record)
        changed = True
    if changed:
        save_index(records)
    return records


def ask_geniex(
    server: str,
    model: str,
    question: str,
    records: list[dict[str, str]],
    history: list[dict[str, str]],
) -> str:
    findings: list[str] = []
    for record in records:
        path = ROOT / record["path"]
        if not path.exists():
            continue
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"Answer the user's question about this image only. Image filename: {record['name']}. "
                    f"Library note: {record.get('note', '')}. Previously indexed visual description: {record.get('description', '')}. "
                    f"The image is attached below. Inspect it directly before answering. Question: {question}"
                ),
            },
            {"type": "image_url", "image_url": {"url": image_data_url(path)}},
        ]
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "You are a precise conversational image assistant. Use only visible evidence from the provided image. If the image does not answer the question, say so. Do not use facts from other images.",
            },
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": content})
        answer = _complete_geniex(server, model, messages)
        if any(phrase in answer.lower() for phrase in VISION_FAILURE_PHRASES) and record.get("description"):
            answer = _answer_from_description(server, model, question, record["description"])
        findings.append(f"{record['name']}: {answer}")

    if not findings:
        return "I could not find any available images to inspect."
    if len(findings) == 1:
        return findings[0].split(": ", 1)[1]

    synthesis = [
        "Answer the user's question using only these per-image findings. Name the relevant image filename when useful. If findings disagree, report the difference instead of choosing one. Do not invent details.",
        f"User question: {question}",
        "Per-image findings:\n" + "\n".join(f"- {finding}" for finding in findings),
    ]
    return _complete_geniex(
        server,
        model,
        [
            {"role": "system", "content": "You synthesize grounded findings from multiple images into a concise conversational answer."},
            *history,
            {"role": "user", "content": "\n\n".join(synthesis)},
        ],
    )


def _complete_geniex(server: str, model: str, messages: list[dict[str, Any]]) -> str:
    payload = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 1024}
    response = requests.post(f"{server.rstrip('/')}/v1/chat/completions", json=payload, timeout=180)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _answer_from_description(server: str, model: str, question: str, description: str) -> str:
    messages = [
        {"role": "system", "content": "Answer only from the provided verified image description. Do not claim that you cannot see an image."},
        {"role": "user", "content": f"Question: {question}\nVerified image description: {description}"},
    ]
    return _complete_geniex(server, model, messages)


def add_uploads(uploaded_files: list[Any], note: str, records: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, int]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    existing_records: list[dict[str, str]] = []
    for record in records:
        if (ROOT / record["path"]).exists():
            existing_records.append(record)
    known_names = {record["name"] for record in existing_records}
    added = 0
    skipped = 0
    for uploaded in uploaded_files:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix.lstrip(".") not in SUPPORTED_TYPES or uploaded.name in known_names:
            skipped += 1
            continue
        destination = IMAGE_DIR / uploaded.name
        destination.write_bytes(uploaded.getbuffer())
        existing_records.append({"name": uploaded.name, "path": destination.relative_to(ROOT).as_posix(), "note": note.strip(), "description": ""})
        known_names.add(uploaded.name)
        added += 1
    save_index(existing_records)
    return existing_records, added, skipped


def main() -> None:
    st.set_page_config(page_title="Gemma Image RAG", page_icon="[img]", layout="wide")
    st.title("Gemma Image RAG")
    st.caption("Ask questions about a local library of images using your cached GenieX VLM.")

    records = load_index()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if records:
        st.session_state.selected_image_index = min(
            st.session_state.get("selected_image_index", 0), len(records) - 1
        )

    with st.sidebar:
        st.header("Connection")
        server = st.text_input("GenieX server", os.getenv("GENIEX_SERVER", DEFAULT_SERVER))
        model = st.text_input("Model", os.getenv("GENIEX_MODEL", DEFAULT_MODEL))
        controller_port = st.text_input("Arduino Uno Q port", os.getenv("ARDUINO_PORT", ""), placeholder="COM5")
        if controller_port:
            if st.session_state.get("controller_port") != controller_port:
                controller_command(controller_port, "ready")
                st.session_state.controller_port = controller_port
            latest_event = st.session_state.get("last_controller_event")
            if latest_event:
                st.caption(f"Arduino: {latest_event.get('event', 'event')} ({latest_event.get('value', 0)})")
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.rerun()
        st.header("Add images")
        uploads = st.file_uploader("Choose images", type=SUPPORTED_TYPES, accept_multiple_files=True)
        note = st.text_area("Shared note for these images", placeholder="Example: receipts from March")
        if st.button("Add to library", type="primary"):
            records, added, skipped = add_uploads(uploads or [], note, records)
            if added:
                st.success(f"Added {added} image(s) to the library.")
            if skipped:
                st.warning(f"Skipped {skipped} unsupported or duplicate file(s).")
            if not uploads:
                st.info("Choose at least one image before clicking Add to library.")
        st.caption(f"{len(records)} image(s) in the local library")

    poll_controller(controller_port, len(records))

    if records:
        selected_image = records[st.session_state.get("selected_image_index", 0)]
        st.subheader(f"Selected image: {selected_image['name']}")
        selected_path = ROOT / selected_image["path"]
        if selected_path.exists():
            st.image(str(selected_path), width=500)
        with st.expander("Image library", expanded=False):
            columns = st.columns(min(4, len(records)))
            for position, record in enumerate(records):
                with columns[position % len(columns)]:
                    path = ROOT / record["path"]
                    if path.exists():
                        st.image(str(path), caption=record["name"], use_container_width=True)
                    if record.get("note"):
                        st.caption(record["note"])
    else:
        st.info("Add one or more images in the sidebar to start asking questions.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    question_draft = st.text_input("Question", key="question_draft", placeholder="Ask about the selected image")
    ask_clicked = st.button("Ask question", type="primary")
    hardware_submit = st.session_state.pop("hardware_submit", False)
    question = question_draft.strip() if ask_clicked or hardware_submit else ""
    if question:
        controller_command(controller_port, "processing")
        try:
            records = enrich_records(server, model, records)
            selected_index = min(st.session_state.get("selected_image_index", 0), len(records) - 1) if records else 0
            selected = [records[selected_index]] if records else retrieve_images(question, records)
        except requests.RequestException as error:
            controller_command(controller_port, "error")
            st.error(f"Could not analyze the library images with GenieX.\n\n{error}")
            return
        if selected:
            st.session_state.last_image_name = selected[0]["name"]
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            if not selected:
                controller_command(controller_port, "error")
                st.write("Add some images first, then ask your question again.")
                return
            with st.spinner(f"Inspecting {len(selected)} retrieved image(s)..."):
                try:
                    answer = ask_geniex(server, model, question, selected, st.session_state.messages[:-1])
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    controller_command(controller_port, "success")
                    st.write(answer)
                    st.caption("Retrieved: " + ", ".join(record["name"] for record in selected))
                except requests.HTTPError as error:
                    controller_command(controller_port, "error")
                    detail = error.response.text.strip() if error.response is not None else str(error)
                    st.error(f"GenieX rejected the request ({error.response.status_code if error.response is not None else 'HTTP error'}).\n\n{detail}")
                except requests.ConnectionError as error:
                    controller_command(controller_port, "error")
                    st.error(f"Could not reach GenieX at {server}. Start `geniex serve` and try again.\n\n{error}")
                except requests.RequestException as error:
                    controller_command(controller_port, "error")
                    st.error(f"The GenieX request failed.\n\n{error}")
                except (KeyError, IndexError, ValueError) as error:
                    controller_command(controller_port, "error")
                    st.error(f"GenieX returned an unexpected response: {error}")


if __name__ == "__main__":
    main()