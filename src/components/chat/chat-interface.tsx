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
    MessageBranchNext,
    MessageBranchPage,
    MessageBranchPrevious,
    MessageBranchSelector,
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
import { AlertTriangleIcon } from "lucide-react";
import { BrainIcon } from "lucide-react";
import type { UIMessage } from "ai";
import { DefaultChatTransport } from "ai";
import { useChat } from "@ai-sdk/react";
import { CheckIcon } from "lucide-react";
import { nanoid } from "nanoid";
import { useCallback, useEffect, useMemo, useState } from "react";
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
    const [model, setModel] = useState<string | undefined>(undefined);
    useEffect(() => {
        if (!model && downloadedLlmModels.length > 0) {
            setModel(downloadedLlmModels[0].id);
        }
    }, [model, downloadedLlmModels]);
    const [modelSelectorOpen, setModelSelectorOpen] = useState(false);
    const [text, setText] = useState<string>("");
    const [showReasoning, setShowReasoning] = useState<boolean>(true);

    const transport = useMemo(() => new DefaultChatTransport({ api: "/api/chat" }), []);
    const { messages, status, stop, sendMessage, clearError } = useChat({
        transport,
        onError: (err) => {
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
                { body: { model, enableThinking: showReasoning } }
            );
            setText("");
        },
        [sendMessage, model, showReasoning]
    );


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
    }, []);

    const isSubmitDisabled = useMemo(
        () => !model || !(text.trim() || status) || status === "streaming",
        [text, status, model]
    );

    return (
        <div className="relative flex h-[calc(100vh-80px)] flex-col divide-y overflow-hidden">
            <Conversation>
                <ConversationContent>
                    {messages.map((message) => {
                        const reasoningPart = message.parts?.find((p) => p.type === "reasoning");
                        const textParts = message.parts?.filter((p) => p.type === "text") || [];
                        const fileParts = message.parts?.filter((p) => p.type === "file") || [];
                        const isReasoningStreaming =
                            (reasoningPart as any)?.state === "streaming";

                        return (
                            <MessageBranch defaultBranch={0} key={message.id}>
                                <MessageBranchContent>
                                    <Message
                                        from={message.role === "user" ? "user" : "assistant"}
                                        key={message.id}
                                    >
                                        <div>
                                            {fileParts.length > 0 && (
                                                <Attachments variant="grid" className="justify-end">
                                                    {fileParts.map((part: any, idx) => (
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
                                                        {(reasoningPart as any).text}
                                                    </ReasoningContent>
                                                </Reasoning>
                                            )}
                                            <MessageContent>
                                                {textParts.map((p: any, i) => (
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
                            <PromptInputSubmit disabled={isSubmitDisabled} status={status} />
                        </PromptInputFooter>
                    </PromptInput>
                </div>
            </div>
        </div>
    );
};
