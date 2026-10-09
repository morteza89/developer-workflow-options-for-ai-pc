"""One disposable agent process. Imported SDKs never run inside the task container."""

import json
import os
from pathlib import Path
import subprocess
import time


def append_event(path, event):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")


def request_options(profile, policy):
    return {"model": profile["model"], "max_tokens": policy["max_output_tokens"], "temperature": policy["temperature"], "timeout": policy.get("request_timeout_seconds", policy["deadline_seconds"]), "extra_body": profile["extra_body"]}


def review_submission(output, connection):
    lines = output.get("output", "").lstrip().splitlines()
    if not lines or lines[0].strip() != "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" or output["returncode"] != 0:
        return
    connection.send({"kind": "submission_check", "at": time.perf_counter()})
    review = connection.recv()
    if not review["accepted"]:
        output.update(returncode=1, output="Submission rejected. Continue repairing and testing, then resubmit.\n" + review["feedback"])


def run_worker(connection, profile, policy, image, container_name, prepared, output):
    output = Path(output)
    os.environ["MSWEA_GLOBAL_CONFIG_DIR"] = str(output / "empty-global-config")
    os.environ["MSWEA_SILENT_STARTUP"] = "1"
    os.environ["MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT"] = "1"
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
    import anthropic
    import httpx
    import litellm
    import openai

    events = output / "events.jsonl"
    client_options = {"max_retries": 0, "http_client": httpx.Client(trust_env=False)}
    if profile["provider"] == "mock":
        client = None
    elif profile["provider"] == "local":
        client = openai.OpenAI(base_url=profile["base_url"], api_key="unused", **client_options)
    else:
        client = anthropic.Anthropic(api_key=os.environ[profile["api_key_env"]], base_url=profile["base_url"], **client_options)

    class RecordedModel(LitellmTextbasedModel):
        mock_index = 0

        def _calculate_cost(self, response):
            return {"cost": 0.0}

        def _query(self, messages, **kwargs):
            if profile["provider"] == "mock":
                if self.mock_index == len(profile["mock_commands"]) and profile.get("mock_wait_after_commands"):
                    connection.recv()
                command = profile["mock_commands"][self.mock_index]
                self.mock_index += 1
                return litellm.ModelResponse(model="offline-mock", choices=[{"message": {"role": "assistant", "content": "```mswea_bash_command\n" + command + "\n```"}, "finish_reason": "stop"}])
            if policy["max_conversation_characters"] is not None and len(json.dumps(messages)) > policy["max_conversation_characters"]:
                raise RuntimeError("Conversation limit exceeded; no truncation permitted")
            started = time.perf_counter()
            limit = "no task deadline" if policy["deadline_seconds"] is None else f"{policy['deadline_seconds']}s total task budget"
            print(f"Requesting {profile['model']} ({limit})...", flush=True)
            append_event(events, {"kind": "request_start", "at": started})
            try:
                options = request_options(profile, policy)
                if profile["provider"] == "local":
                    response = client.chat.completions.create(messages=messages, **options)
                    text = response.choices[0].message.content or ""
                    finish = response.choices[0].finish_reason
                else:
                    response = client.messages.create(system=messages[0]["content"], messages=messages[1:], **options)
                    text = "".join(block.text for block in response.content if block.type == "text")
                    finish = response.stop_reason
                append_event(events, {"kind": "request_end", "at": time.perf_counter(), "seconds": time.perf_counter() - started, "model": response.model, "usage": response.usage.model_dump() if response.usage else None, "response_id": response.id, "finish_reason": finish, "content": text})
                print(f"Model response received in {time.perf_counter() - started:.1f}s.", flush=True)
                if response.model != profile["expected_returned_model"]:
                    append_event(events, {"kind": "identity_mismatch", "expected": profile["expected_returned_model"], "returned": response.model})
                    raise RuntimeError("Returned model identity mismatch")
                return litellm.ModelResponse(model=response.model, choices=[{"message": {"role": "assistant", "content": text}, "finish_reason": finish}])
            except Exception as error:
                append_event(events, {"kind": "request_error", "at": time.perf_counter(), "seconds": time.perf_counter() - started, "error_type": type(error).__name__})
                raise RuntimeError(f"Model request failed: {type(error).__name__}") from None

    class RecordedEnvironment(DockerEnvironment):
        def _start_container(self):
            self.container_id = container_name
            subprocess.run(["docker", "run", "-d", "--name", container_name, "--network", "none", "--read-only", "--cap-drop", "ALL", "--cap-add", "CHOWN", "--security-opt", "no-new-privileges", "--pids-limit", "128", "--cpus", str(policy["container_cpus"]), "--memory", policy["container_memory"], "--tmpfs", "/tmp:rw,nosuid,size=128m", "--mount", f"type=volume,src={container_name}-task,dst=/task", image, "tail", "-f", "/dev/null"], check=True, capture_output=True, timeout=60)
            subprocess.run(["docker", "cp", str(Path(prepared)) + "/.", container_name + ":/task"], check=True, capture_output=True, timeout=30)
            subprocess.run(["docker", "exec", "--user", "0", container_name, "chown", "-R", "10001:10001", "/task"], check=True, capture_output=True, timeout=30)

        def cleanup(self):
            pass

        def _check_finished(self, output):
            if policy["deadline_seconds"] is None:
                review_submission(output, connection)
            super()._check_finished(output)

        def execute(self, action, cwd="", **kwargs):
            started = time.perf_counter()
            append_event(events, {"kind": "tool_start", "at": started, "command": action.get("command", "")})
            try:
                result = super().execute(action, cwd=cwd, **kwargs)
                append_event(events, {"kind": "tool_result", "at": time.perf_counter(), "returncode": result["returncode"]})
                return result
            finally:
                append_event(events, {"kind": "tool_end", "at": time.perf_counter(), "seconds": time.perf_counter() - started})

    try:
        model = RecordedModel(model_name=profile["model"], cost_tracking="ignore_errors", litellm_model_registry=None, format_error_template=policy["format_error_template"])
        environment = RecordedEnvironment(image=image, cwd="/task", timeout=policy["tool_timeout_seconds"] + 2, interpreter=["timeout", "-k", "1", str(policy["tool_timeout_seconds"]), "bash", "-lc"])
        agent = DefaultAgent(model, environment, system_template=policy["system_template"], instance_template=policy["instance_template"], step_limit=policy["step_limit"], cost_limit=0, wall_time_limit_seconds=0, max_consecutive_format_errors=0, output_path=output / "trajectory.json")
        task = (Path(prepared) / "TASK.md").read_text(encoding="utf-8")
        connection.send({"kind": "ready"})
        connection.recv()
        started = time.perf_counter()
        connection.send({"kind": "started", "at": started})
        result = agent.run(task)
        connection.send({"kind": "finished", "at": time.perf_counter(), "result": result})
    except Exception as error:
        connection.send({"kind": "error", "at": time.perf_counter(), "error_type": type(error).__name__})
    finally:
        if client is not None:
            client.close()
        connection.close()