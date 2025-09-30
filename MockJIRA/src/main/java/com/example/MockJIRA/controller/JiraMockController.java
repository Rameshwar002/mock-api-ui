package com.example.MockJIRA.controller;

import com.example.MockJIRA.DTOs.JiraTicketResponse;
import com.example.MockJIRA.service.JiraMockService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/mock/api") // Mimics the base path of the Jira API
public class JiraMockController {

    private final JiraMockService jiraMockService;

    public JiraMockController(JiraMockService jiraMockService) {
        this.jiraMockService = jiraMockService;
    }

    @GetMapping("/{ticketId}")
    public ResponseEntity<JiraTicketResponse> getJiraTicket(@PathVariable String ticketId) {
        JiraTicketResponse ticket = jiraMockService.getTicketById(ticketId);
        return ResponseEntity.ok(ticket);
    }
}

