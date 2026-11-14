"use client";

import {
    Attachment,
    type AttachmentData,
    AttachmentPreview,
    AttachmentRemove,
    Attachments,
} from "@/components/ai-elements/attachments";
import {
    Conversation,
    ConversationContent,
    ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
    Message,
    MessageBranch,
    MessageBranchContent,
    MessageContent,
    MessageResponse,
} from "@/components/ai-elements/message";
import {
    ModelSelector,
    ModelSelectorContent,
    ModelSelectorEmpty,
    ModelSelectorGroup,
    ModelSelectorInput,
    ModelSelectorItem,
    ModelSelectorList,
    ModelSelectorLogo,
    ModelSelectorName,
    ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector";
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import {
    PromptInput,
    PromptInputActionAddAttachments,
    PromptInputActionMenu,
    PromptInputActionMenuContent,
    PromptInputActionMenuTrigger,
    PromptInputBody,
    PromptInputButton,
    PromptInputFooter,
    PromptInputHeader,
    PromptInputSubmit,
    PromptInputTextarea,
    PromptInputTools,
    usePromptInputAttachments,
} from "@/components/ai-elements/prompt-input";
import {
    Reasoning,
    ReasoningContent,
    ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import { SpeechInput } from "@/components/ai-elements/speech-input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useModelCatalog, type ModelCatalogEntry } from "@/hooks/use-model-catalog";
import Link from "next/link";
import { AlertTriangleIcon, BrainIcon, CheckIcon, ShieldCheckIcon, SparklesIcon } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useChat } from "@ai-sdk/react";
import { AgentMessagePart } from "@/components/chat/agent-parts";
import { TrajectoryPanel } from "@/components/trajectory/trajectory-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { extractTrajectoryEventsFromMessages } from "@/hooks/use-trajectory-stream";
import { toast } from "sonner";
const AttachmentItem = ({
    attachment,
    onRemove,
}: {
    attachment: AttachmentData;
    onRemove: (id: string) => void;
}) => {
    const handleRemove = useCallback(() => {
        onRemove(attachment.id);
    }, [onRemove, attachment.id]);

    return (
        <Attachment data={attachment} onRemove={handleRemove}>
            <AttachmentPreview />
            <AttachmentRemove />
        </Attachment>
    );
};

const PromptInputAttachmentsDisplay = () => {
    const attachments = usePromptInputAttachments();

    const handleRemove = useCallback(
        (id: string) => {
            attachments.remove(id);
        },
        [attachments]
    );

    if (attachments.files.length === 0) {
        return null;
    }

    return (
        <Attachments variant="inline">
            {attachments.files.map((attachment) => (
                <AttachmentItem
                    attachment={attachment}
                    key={attachment.id}
                    onRemove={handleRemove}
                />
            ))}
        </Attachments>
    );
};

const ModelItem = ({
    m,
    isSelected,
    onSelect,
}: {
    m: ModelCatalogEntry;
    isSelected: boolean;
    onSelect: (id: string) => void;
}) => {
    const handleSelect = useCallback(() => {
        onSelect(m.id);
    }, [onSelect, m.id]);

    return (
        <ModelSelectorItem onSelect={handleSelect} value={m.id}>
            <ModelSelectorLogo provider="google" />
            <ModelSelectorName>{m.name}</ModelSelectorName>
            {isSelected ? (
                <CheckIcon className="ml-auto size-4" />
            ) : (
                <div className="ml-auto size-4" />
            )}
        </ModelSelectorItem>
    );
};

export default function ChatInterface() {
    const { catalog, states } = useModelCatalog();
    const downloadedLlmModels = useMemo(
        () =>
            catalog.filter(
                (m) => m.category === "llm" && states[m.id]?.status === "completed"
            ),
        [catalog, states]
    );
    const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);
    const model = selectedModel ?? downloadedLlmModels[0]?.id;
    const setModel = setSelectedModel;
    const [modelSelectorOpen, setModelSelectorOpen] = useState(false);
    const [text, setText] = useState<string>("");
    const [showReasoning, setShowReasoning] = useState<boolean>(true);
    const [egmMode, setEgmMode] = useState<boolean>(false);
    const [harnessCalibrate, setHarnessCalibrate] = useState<boolean>(false);

    const transport = useMemo(() => new DefaultChatTransport({ api: "/api/chat" }), []);
    const { messages, status, stop, sendMessage, clearError } = useChat({
        transport,
        onError: (err: Error) => {
            toast.error("Couldn't get a response", {
                description:
                    err.message ||
                    "The model may not support image input, or the backend is unreachable.",
            });
            clearError();
        },
    });

    const selectedModelData = useMemo(
        () => downloadedLlmModels.find((m) => m.id === model),
        [downloadedLlmModels, model]
    );

    const handleSubmit = useCallback(
        (message: PromptInputMessage) => {
            const hasText = Boolean(message.text);
            const hasAttachments = Boolean(message.files?.length);

            if (!(hasText || hasAttachments)) {
                return;
            }

            void sendMessage(
                { text: message.text, files: message.files },
                { body: { model, enableThinking: showReasoning, egmMode, harnessCalibrate } }
            );
            setText("");
        },
        [sendMessage, model, showReasoning, egmMode, harnessCalibrate]
    );

    const toggleEgmMode = useCallback(() => {
        setEgmMode((prev) => !prev);
    }, []);

    const toggleHarnessCalibrate = useCallback(() => {
        setHarnessCalibrate((prev) => !prev);
    }, []);


    const handleTranscriptionChange = useCallback((transcript: string) => {
        setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
    }, []);

    const handleTextChange = useCallback(
        (event: React.ChangeEvent<HTMLTextAreaElement>) => {
            setText(event.target.value);
        },
        []
    );

    const toggleReasoning = useCallback(() => {
        setShowReasoning((prev) => !prev);
    }, []);

    const handleModelSelect = useCallback((modelId: string) => {
        setModel(modelId);
        setModelSelectorOpen(false);
    }, [setModel]);

    const isSubmitDisabled = useMemo(() => {
        if (!model) return true;
        if (status === "streaming" || status === "submitted") return false; // allow Stop
        return !text.trim();
    }, [text, status, model]);

    const activeStatusText = useMemo(() => {
        if (status === "submitted") return "Agent initializing...";
        if (status === "streaming") return "Agent executing state machine...";
        return "";
    }, [status]);

    const trajectoryEvents = useMemo(
        () => extractTrajectoryEventsFromMessages(messages),
        [messages]
    );

    return (
        <div className="relative flex h-[calc(100vh-80px)] flex-col divide-y overflow-hidden">
            <Tabs defaultValue="conversation" className="flex min-h-0 flex-1 flex-col">
                <div className="flex items-center justify-between border-b border-border bg-card px-4 py-1.5">
                    <TabsList variant="line">
                        <TabsTrigger value="conversation">Conversation</TabsTrigger>
                        <TabsTrigger value="trajectory">
                            Trajectory{trajectoryEvents.length > 0 ? ` (${trajectoryEvents.length})` : ""}
                        </TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="conversation" className="flex min-h-0 flex-1 flex-col">
            <Conversation>
                <ConversationContent>
                    {messages.map((message: UIMessage) => {
                        const reasoningPart = message.parts?.find((p) => (p as { type: string }).type === "reasoning") as { state?: string; text?: string } | undefined;
                        const textParts = (message.parts?.filter((p) => (p as { type: string }).type === "text") || []) as Array<{ text: string }>;
                        const fileParts = (message.parts?.filter((p) => (p as { type: string }).type === "file") || []) as Array<AttachmentData>;
                        const otherParts = (message.parts?.filter((p) => {
                            const t = (p as { type: string }).type;
                            return t !== "text" && t !== "reasoning" && t !== "file" && t !== "data-trajectory";
                        }) || []) as Array<Record<string, unknown>>;
                        const isReasoningStreaming = reasoningPart?.state === "streaming";

                        return (
                            <MessageBranch defaultBranch={0} key={message.id}>
                                <MessageBranchContent>
                                    <Message
                                        from={message.role === "user" ? "user" : "assistant"}
                                        key={message.id}
                                    >
                                        <div className="w-full">
                                            {fileParts.length > 0 && (
                                                <Attachments variant="grid" className="justify-end">
                                                    {fileParts.map((part, idx) => (
                                                        <Attachment
                                                            data={{ ...part, id: `${message.id}-file-${idx}` }}
                                                            key={idx}
                                                        >
                                                            <AttachmentPreview />
                                                        </Attachment>
                                                    ))}
                                                </Attachments>
                                            )}
                                            {reasoningPart && showReasoning && (
                                                <Reasoning isStreaming={isReasoningStreaming}>
                                                    <ReasoningTrigger />
                                                    <ReasoningContent>
                                                        {reasoningPart.text || ""}
                                                    </ReasoningContent>
                                                </Reasoning>
                                            )}
                                            {otherParts.length > 0 && (
                                                <div className="my-2 space-y-2">
                                                    {otherParts.map((part, idx: number) => (
                                                        <AgentMessagePart key={idx} part={part} />
                                                    ))}
                                                </div>
                                            )}
                                            <MessageContent>
                                                {textParts.map((p, i) => (
                                                    <MessageResponse key={i}>{p.text}</MessageResponse>
                                                ))}
                                            </MessageContent>
                                        </div>
                                    </Message>
                                </MessageBranchContent>
                            </MessageBranch>
                        );
                    })}
                </ConversationContent>
                <ConversationScrollButton />
            </Conversation>
                </TabsContent>

                <TabsContent value="trajectory" className="min-h-0 flex-1">
                    <TrajectoryPanel
                        events={trajectoryEvents}
                        mode="live"
                        isStreaming={status === "streaming" || status === "submitted"}
                    />
                </TabsContent>
            </Tabs>
            <div className="grid shrink-0 gap-4 pt-4">
                <div className="w-full px-4 pb-4">
                    {downloadedLlmModels.length === 0 && (
                        <Alert className="mb-4">
                            <AlertTriangleIcon />
                            <AlertTitle>No model downloaded</AlertTitle>
                            <AlertDescription>
                                Download a model before you can start chatting.{" "}
                                <Link href="/downloads" className="underline">
                                    Go to the Downloads page
                                </Link>
                                .
                            </AlertDescription>
                        </Alert>
                    )}
                    <PromptInput
                        accept="image/png,image/jpeg,image/bmp,image/gif"
                        globalDrop
                        maxFiles={4}
                        maxFileSize={10 * 1024 * 1024}
                        multiple
                        onError={(err) => toast.error(err.message)}
                        onSubmit={handleSubmit}
                    >
                        <PromptInputHeader>
                            <PromptInputAttachmentsDisplay />
                        </PromptInputHeader>
                        <PromptInputBody>
                            <PromptInputTextarea onChange={handleTextChange} value={text} />
                        </PromptInputBody>
                        <PromptInputFooter>
                            <PromptInputTools>
                                <PromptInputActionMenu>
                                    <PromptInputActionMenuTrigger />
                                    <PromptInputActionMenuContent>
                                        <PromptInputActionAddAttachments />
                                    </PromptInputActionMenuContent>
                                </PromptInputActionMenu>
                                <SpeechInput
                                    className="shrink-0"
                                    onTranscriptionChange={handleTranscriptionChange}
                                    size="icon-sm"
                                    variant="ghost"
                                />
                                <PromptInputButton
                                    onClick={toggleReasoning}
                                    variant={showReasoning ? "default" : "ghost"}
                                >
                                    <BrainIcon size={16} />
                                    <span>Reasoning</span>
                                </PromptInputButton>
                                <PromptInputButton
                                    onClick={toggleEgmMode}
                                    variant={egmMode ? "default" : "ghost"}
                                    title="Spec-first coding with dual Elephant (Architect) and Goldfish (Reviewer) model"
                                    aria-label="Toggle Elephant-Goldfish Spec-First Mode"
                                >
                                    <ShieldCheckIcon size={16} />
                                    <span>EGM Spec-First</span>
                                </PromptInputButton>
                                <PromptInputButton
                                    onClick={toggleHarnessCalibrate}
                                    variant={harnessCalibrate ? "default" : "ghost"}
                                    title="Run Level 1 Propose-Probe-Compose calibration before planning"
                                    aria-label="Toggle Harness2 Calibration"
                                    aria-pressed={harnessCalibrate}
                                >
                                    <SparklesIcon size={16} />
                                    <span>Calibrate Harness</span>
                                </PromptInputButton>
                                <ModelSelector
                                    onOpenChange={setModelSelectorOpen}
                                    open={modelSelectorOpen}
                                >
                                    <ModelSelectorTrigger render={<PromptInputButton />}>
                                        {selectedModelData && (
                                            <ModelSelectorLogo provider="google" />
                                        )}
                                        {selectedModelData?.name && (
                                            <ModelSelectorName>
                                                {selectedModelData.name}
                                            </ModelSelectorName>
                                        )}
                                    </ModelSelectorTrigger>
                                    <ModelSelectorContent>
                                        <ModelSelectorInput placeholder="Search models..." />
                                        <ModelSelectorList>
                                            <ModelSelectorEmpty>No models found.</ModelSelectorEmpty>
                                            <ModelSelectorGroup heading="Google">
                                                {downloadedLlmModels.map((m) => (
                                                    <ModelItem
                                                        isSelected={model === m.id}
                                                        key={m.id}
                                                        m={m}
                                                        onSelect={handleModelSelect}
                                                    />
                                                ))}
                                            </ModelSelectorGroup>
                                        </ModelSelectorList>
                                    </ModelSelectorContent>
                                </ModelSelector>
                            </PromptInputTools>
                            <div aria-live="polite" className="sr-only">{activeStatusText}</div>
                            <PromptInputSubmit disabled={isSubmitDisabled} onStop={stop} status={status} />
                        </PromptInputFooter>
                    </PromptInput>
                </div>
            </div>
        </div>
    );
};
