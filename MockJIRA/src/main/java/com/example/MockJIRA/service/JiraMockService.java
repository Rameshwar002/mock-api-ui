package com.example.MockJIRA.service;


import com.example.MockJIRA.DTOs.JiraTicketResponse;
import com.example.MockJIRA.ExceptionsHandler.ResourceNotFoundException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class JiraMockService {


    private static final Map<String, JiraTicketResponse> ticketDatabase = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

   //loaded the data directly in json
    @PostConstruct
    public void init() {
        try {
            InputStream inputStream = TypeReference.class.getResourceAsStream("/data/mock-jira-tickets.json");
            Map<String, JiraTicketResponse> loadedTickets = objectMapper.readValue(inputStream, new TypeReference<>() {});
            ticketDatabase.putAll(loadedTickets);
            System.out.println("Loaded " + ticketDatabase.size() + " mock Jira tickets.");
        } catch (Exception e) {
            // In a real app, handle this more gracefully.
            throw new RuntimeException("Failed to load mock Jira tickets", e);
        }
    }

    public JiraTicketResponse getTicketById(String ticketId) {
        if (!ticketDatabase.containsKey(ticketId)) {
            throw new ResourceNotFoundException("Ticket not found with id: " + ticketId);
        }
        return ticketDatabase.get(ticketId);
    }
}

