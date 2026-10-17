
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#chat-form");
    const input = document.querySelector("#message-input");
    const chatContainer = document.querySelector("#messages");
    const modeSelect = document.querySelector("#mode");
    const scenarioSelect = document.querySelector("#scenario");
    const startScenarioButton = document.querySelector("#start-scenario");
    const statusBadge = document.querySelector("#connection-status");

    if (!form || !input || !chatContainer) {
        console.error(
            "Chat form, input, or message container was not found."
        );
        return;
    }

    const conversation = [];
    let waitingForResponse = false;

    // Safely read JSON responses, including handling HTML error pages.
    async function readJsonResponse(response, requestName) {
        const raw = await response.text();
        let data;

        try {
            data = JSON.parse(raw);
        } catch (error) {
            console.error(
                `${requestName}: Expected JSON but received:`,
                {
                    status: response.status,
                    contentType: response.headers.get("content-type"),
                    body: raw.slice(0, 1000)
                }
            );

            throw new Error(
                `The server returned an invalid response (HTTP ${response.status}). ` +
                "Check the Flask terminal for the server error."
            );
        }

        if (!response.ok) {
            throw new Error(
                data.error ||
                data.message ||
                `${requestName} failed (HTTP ${response.status}).`
            );
        }

        return data;
    }

    function renderMessage(role, text) {
        const article = document.createElement("article");
        article.className = `message ${role}`;

        const avatar = document.createElement("div");
        avatar.className = "avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = role === "user" ? "Y" : "R";

        const content = document.createElement("div");
        content.className = "message-content";

        const label = document.createElement("div");
        label.className = "message-label";
        label.textContent =
            role === "user"
                ? "You"
                : "Research Readiness Assistant";

        const bubble = document.createElement("div");
        bubble.className = "bubble";

        const messageText = document.createElement("div");
        messageText.className = "message-text";

        if (role === "user") {
            // Display user messages as plain text.
            // This preserves line breaks, numbering, symbols, and spacing.
            // textContent also prevents user input from being interpreted as HTML.
            messageText.textContent = String(text);
            messageText.style.whiteSpace = "pre-wrap";
            messageText.style.overflowWrap = "anywhere";
        } else if (
            typeof marked !== "undefined" &&
            typeof DOMPurify !== "undefined"
        ) {
            // Render assistant responses as Markdown.
            messageText.innerHTML = DOMPurify.sanitize(
                marked.parse(String(text))
            );

            // Only allow HTTP and HTTPS links.
            messageText.querySelectorAll("a[href]").forEach((link) => {
                const href = link.getAttribute("href");

                if (!href || !/^https?:\/\//i.test(href)) {
                    link.removeAttribute("href");
                    return;
                }

                link.target = "_blank";
                link.rel = "noopener noreferrer";
            });
        } else {
            // Fallback if Markdown libraries are unavailable.
            messageText.textContent = String(text);
            messageText.style.whiteSpace = "pre-wrap";
            messageText.style.overflowWrap = "anywhere";
        }

        bubble.appendChild(messageText);
        content.appendChild(label);
        content.appendChild(bubble);
        article.appendChild(avatar);
        article.appendChild(content);
        chatContainer.appendChild(article);

        chatContainer.scrollTop = chatContainer.scrollHeight;

        return article;
    }

    function renderLoading() {
        const article = document.createElement("article");
        article.className = "message assistant loading-message";

        const avatar = document.createElement("div");
        avatar.className = "avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = "R";

        const content = document.createElement("div");
        content.className = "message-content";

        const label = document.createElement("div");
        label.className = "message-label";
        label.textContent = "Research Readiness Assistant";

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.textContent = "Thinking…";

        content.appendChild(label);
        content.appendChild(bubble);
        article.appendChild(avatar);
        article.appendChild(content);
        chatContainer.appendChild(article);

        chatContainer.scrollTop = chatContainer.scrollHeight;

        return article;
    }

    async function checkConfiguration() {
        if (!statusBadge) return;

        try {
            const response = await fetch("/api/config");
            const data = await readJsonResponse(
                response,
                "Configuration check"
            );

            const configured =
                data.model_configured ??
                data.configured ??
                data.ready ??
                data.ok;

            if (configured === true) {
                statusBadge.textContent = "Model configuration ready";
                statusBadge.classList.remove("error", "status-error");
                statusBadge.classList.add("connected");
            } else if (configured === false) {
                statusBadge.textContent = "Model configuration missing";
                statusBadge.classList.remove("connected");
                statusBadge.classList.add("error", "status-error");
            } else {
                statusBadge.textContent =
                    "Configuration status unavailable";
            }
        } catch (error) {
            console.error("Configuration check failed:", error);

            statusBadge.textContent =
                "Could not check model configuration";

            statusBadge.classList.remove("connected");
            statusBadge.classList.add("error", "status-error");
        }
    }

    async function sendMessage(messageOverride = null) {
        if (waitingForResponse) return;

        const message = (
            typeof messageOverride === "string"
                ? messageOverride
                : input.value
        ).trim();

        if (!message) return;

        // Save the original message without Markdown conversion.
        conversation.push({
            role: "user",
            content: message
        });

        renderMessage("user", message);

        input.value = "";
        input.style.height = "auto";
        waitingForResponse = true;

        const sendButton = form.querySelector(
            'button[type="submit"], input[type="submit"]'
        );

        const suggestionButtons = document.querySelectorAll(
            "#suggestions .suggestion[data-message]"
        );

        if (sendButton) sendButton.disabled = true;

        if (startScenarioButton) {
            startScenarioButton.disabled = true;
        }

        suggestionButtons.forEach((button) => {
            button.disabled = true;
        });

        const loading = renderLoading();

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    messages: conversation.slice(-30),
                    mode: modeSelect
                        ? modeSelect.value
                        : "experimental",
                    scenario: scenarioSelect
                        ? scenarioSelect.value
                        : "none"
                })
            });

            const data = await readJsonResponse(
                response,
                "Chat request"
            );

            const reply =
                typeof data.reply === "string" && data.reply.trim()
                    ? data.reply
                    : "The assistant returned an empty response.";

            conversation.push({
                role: "assistant",
                content: reply
            });

            renderMessage("assistant", reply);
        } catch (error) {
            console.error("Chat request failed:", error);

            renderMessage(
                "assistant",
                `Sorry, something went wrong: ${
                    error.message || "Please try again."
                }`
            );

            // Remove the failed user message from conversation history.
            if (
                conversation.length > 0 &&
                conversation[conversation.length - 1].role === "user"
            ) {
                conversation.pop();
            }
        } finally {
            loading.remove();
            waitingForResponse = false;

            if (sendButton) sendButton.disabled = false;

            if (startScenarioButton) {
                startScenarioButton.disabled = false;
            }

            suggestionButtons.forEach((button) => {
                button.disabled = false;
            });

            input.focus();
        }
    }

    // Handle the normal chat form submission.
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        sendMessage();
    });

    // Handle suggested prompt buttons.
    document.querySelectorAll(
        "#suggestions .suggestion[data-message]"
    ).forEach((button) => {
        button.addEventListener("click", () => {
            sendMessage(button.dataset.message);
        });
    });

    // Start the selected practice scenario, if the controls exist.
    if (startScenarioButton) {
        startScenarioButton.addEventListener("click", () => {
            if (waitingForResponse) return;

            const scenarioId = scenarioSelect
                ? scenarioSelect.value
                : "none";

            if (scenarioId === "none") {
                sendMessage(
                    "Help me begin a research-readiness practice session. " +
                    "Ask me about my research goals, experience, and skills " +
                    "one question at a time."
                );
                return;
            }

            const option = scenarioSelect.options[
                scenarioSelect.selectedIndex
            ];

            const scenarioName = option
                ? option.textContent.trim()
                : scenarioId;

            sendMessage(
                `Let's begin the "${scenarioName}" practice scenario. ` +
                "Guide me through it step by step and ask me the first question."
            );
        });
    }

    // Enter sends; Shift+Enter adds a newline in a textarea.
    input.addEventListener("keydown", (event) => {
        if (
            event.key === "Enter" &&
            !event.shiftKey &&
            input.tagName.toLowerCase() === "textarea"
        ) {
            event.preventDefault();
            sendMessage();
        }
    });

    checkConfiguration();
});
