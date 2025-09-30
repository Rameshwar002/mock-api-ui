package com.example.MockJIRA.DTOs;

import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.List;

@Data
@NoArgsConstructor
public class JiraTicketResponse {
    private String id;
    private String key;
    private String self;
    private Fields fields;
}

@Data
@NoArgsConstructor
class Fields {
    private String summary;
    private IssueType issuetype;
    private Project project;
    private Status status;
    private Priority priority;
    private User assignee;
    private User reporter;
    private Description description;
    private String created;
    private String updated;
    private List<Attachment> attachment;
}

@Data
@NoArgsConstructor
class Attachment {
    private String id;
    private String self;
    private String filename;
    private User author;
    private String created;
    private long size;
    private String mimeType;
    private String content;
    private String thumbnail;
}

@Data
@NoArgsConstructor
class User {
    private String displayName;
    private String emailAddress;
}

@Data
@NoArgsConstructor
class IssueType {
    private String id;
    private String name;
    private String iconUrl;
}

@Data
@NoArgsConstructor
class Project {
    private String id;
    private String key;
    private String name;
}

@Data
@NoArgsConstructor
class Status {
    private String name;
    private String id;
}

@Data
@NoArgsConstructor
class Priority {
    private String name;
    private String id;
}

@Data
@NoArgsConstructor
class Description {
    private String type = "doc";
    private int version = 1;
    private List<ContentNode> content;
}

@Data
@NoArgsConstructor
class ContentNode {
    private String type = "paragraph";
    private List<TextNode> content;
}

@Data
@NoArgsConstructor
class TextNode {
    private String type = "text";
    private String text;
}


