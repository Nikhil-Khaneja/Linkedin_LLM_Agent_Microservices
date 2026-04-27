const swaggerJsdoc = require('swagger-jsdoc');
const swaggerUi = require('swagger-ui-express');

const spec = {
  openapi: '3.0.0',
  info: {
    title: 'Messaging Service API',
    version: '1.0.0',
    description: 'Owner 6 — LinkedIn Distributed System\nBase URL: http://localhost:3006',
  },
  servers: [{ url: 'http://localhost:3006', description: 'Local Docker' }],
  components: {
    securitySchemes: {
      bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT', description: 'Get token from POST /auth/login at localhost:3001' }
    }
  },
  paths: {
  "/threads/open": {
    "post": {
      "tags": [
        "Threads"
      ],
      "summary": "Open/create a thread",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "participant_ids": [
                  "usr_xxx",
                  "usr_yyy"
                ]
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/threads/get": {
    "post": {
      "tags": [
        "Threads"
      ],
      "summary": "Get thread metadata",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "thread_id": "thr_xxx"
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/threads/byUser": {
    "post": {
      "tags": [
        "Threads"
      ],
      "summary": "Get threads for user",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {}
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/messages/list": {
    "post": {
      "tags": [
        "Messages"
      ],
      "summary": "List messages in thread",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "thread_id": "thr_xxx",
                "page_size": 20
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/messages/send": {
    "post": {
      "tags": [
        "Messages"
      ],
      "summary": "Send a message",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "thread_id": "thr_xxx",
                "text": "Hello! I saw your profile and wanted to connect."
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/connections/request": {
    "post": {
      "tags": [
        "Connections"
      ],
      "summary": "Send connection request",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "receiver_id": "usr_xxx",
                "message": "Hi, I would like to connect"
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/connections/accept": {
    "post": {
      "tags": [
        "Connections"
      ],
      "summary": "Accept connection request",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "request_id": "req_xxx"
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/connections/reject": {
    "post": {
      "tags": [
        "Connections"
      ],
      "summary": "Reject connection request",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "request_id": "req_xxx"
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/connections/list": {
    "post": {
      "tags": [
        "Connections"
      ],
      "summary": "List my connections",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {}
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  },
  "/connections/mutual": {
    "post": {
      "tags": [
        "Connections"
      ],
      "summary": "Mutual connections with another user",
      "security": [
        {
          "bearerAuth": []
        }
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "example": {
                "other_id": "usr_xxx"
              }
            }
          }
        }
      },
      "responses": {
        "200": {
          "description": "Success"
        },
        "400": {
          "description": "Validation error"
        },
        "401": {
          "description": "Unauthorized"
        },
        "429": {
          "description": "Rate limited"
        },
        "500": {
          "description": "Server error"
        }
      }
    }
  }
}
};

module.exports = { swaggerUi, spec };
