const swaggerJsdoc = require('swagger-jsdoc');
const swaggerUi = require('swagger-ui-express');

const spec = {
  openapi: '3.0.0',
  info: {
    title: 'Member Service API',
    version: '1.0.0',
    description: 'Owner 2 — LinkedIn Distributed System\nBase URL: http://localhost:3002',
  },
  servers: [{ url: 'http://localhost:3002', description: 'Local Docker' }],
  components: {
    securitySchemes: {
      bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT', description: 'Get token from POST /auth/login at localhost:3001' }
    }
  },
  paths: {
  "/members/create": {
    "post": {
      "tags": [
        "Member"
      ],
      "summary": "Create member profile",
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
                "first_name": "Ava",
                "last_name": "Shah",
                "email": "ava.shah@example.com",
                "city": "San Jose",
                "state": "CA",
                "headline": "Senior Software Engineer",
                "skills": [
                  "Python",
                  "Kafka"
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
  "/members/get": {
    "post": {
      "tags": [
        "Member"
      ],
      "summary": "Get member profile",
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
                "member_id": "mbr_xxx"
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
  "/members/update": {
    "post": {
      "tags": [
        "Member"
      ],
      "summary": "Update member profile",
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
                "member_id": "mbr_xxx",
                "headline": "Updated headline"
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
  "/members/delete": {
    "post": {
      "tags": [
        "Member"
      ],
      "summary": "Delete member profile",
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
                "member_id": "mbr_xxx"
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
  "/members/search": {
    "post": {
      "tags": [
        "Member"
      ],
      "summary": "Search members",
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
                "keyword": "Python engineer",
                "city": "San Jose"
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
