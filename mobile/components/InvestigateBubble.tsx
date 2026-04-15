import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useMarkdown } from "react-native-marked";

interface InvestigateBubbleProps {
  role: "user" | "agent";
  content: string;
  isStreaming: boolean;
}

/**
 * Chat message bubble for the investigation screen.
 *
 * User messages: right-aligned, blue background, plain text.
 * Agent messages: left-aligned, dark background, markdown rendered
 * via react-native-marked's useMarkdown hook (avoids nested FlatList
 * conflict with the outer chat FlatList).
 *
 * When agent content is empty and still streaming, shows "Thinking..."
 * in italic gray text.
 */
export function InvestigateBubble({
  role,
  content,
  isStreaming,
}: InvestigateBubbleProps) {
  if (role === "user") {
    return (
      <View style={styles.userBubble}>
        <Text style={styles.userText}>{content}</Text>
      </View>
    );
  }

  return (
    <View style={styles.agentBubble}>
      {content ? (
        <AgentMarkdown content={content} />
      ) : isStreaming ? (
        <Text style={styles.thinkingText}>Thinking...</Text>
      ) : null}
    </View>
  );
}

/**
 * Renders markdown content using the useMarkdown hook directly,
 * avoiding FlatList nesting issues. The hook returns ReactNode[]
 * which we render in a plain View.
 */
function AgentMarkdown({ content }: { content: string }) {
  const elements = useMarkdown(content, {
    colorScheme: "dark",
    theme: {
      colors: {
        text: "#ffffff",
        code: "#2a2a3e",
        link: "#4a90d9",
        border: "#333333",
      },
    },
  });

  return (
    <View style={styles.markdownContainer}>
      {React.Children.map(elements, (child, i) => (
        <React.Fragment key={`md-${i}`}>{child}</React.Fragment>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: "#4a90d9",
    borderRadius: 16,
    padding: 12,
    marginVertical: 4,
    marginHorizontal: 16,
    maxWidth: "80%",
  },
  agentBubble: {
    alignSelf: "flex-start",
    backgroundColor: "#1a1a2e",
    borderRadius: 16,
    padding: 12,
    marginVertical: 4,
    marginHorizontal: 16,
    maxWidth: "90%",
  },
  userText: {
    color: "#ffffff",
    fontSize: 16,
    lineHeight: 22,
  },
  thinkingText: {
    color: "#888888",
    fontSize: 14,
    fontStyle: "italic",
  },
  markdownContainer: {
    // No additional styling needed -- useMarkdown handles layout
  },
});
