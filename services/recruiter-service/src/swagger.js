const swaggerUi = require('swagger-ui-express');

const errorExample = (code, message, details = {}, retryable = false) => ({
  success: false,
  trace_id: 'trc_example',
  error: {
    code,
    message,
    details,
    retryable
  }
});

const spec = {
  openapi: '3.0.0',
  info: {
    title: 'Recruiter and Company Service API',
    version: '1.0.0',
    description: 'Owner 3 service for recruiter identity, company metadata, and recruiter access-level management.'
  },
  servers: [
    {
      url: 'http://localhost:3003',
      description: 'Local Docker'
    }
  ],
  components: {
    securitySchemes: {
      bearerAuth: {
        type: 'http',
        scheme: 'bearer',
        bearerFormat: 'JWT',
        description: 'JWT issued by Owner 1 auth service'
      }
    }
  },
  security: [{ bearerAuth: [] }],
  paths: {
    '/recruiters/create': {
      post: {
        tags: ['Recruiters'],
        summary: 'Create recruiter identity and company association records',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              example: {
                recruiter_id: 'rec_120',
                name: 'Morgan Lee',
                email: 'morgan@example.com',
                phone: '+14085550000',
                company_name: 'Northstar Labs',
                company_industry: 'Software',
                company_size: 'medium',
                access_level: 'admin'
              }
            }
          }
        },
        responses: {
          201: {
            description: 'Recruiter created',
            content: {
              'application/json': {
                example: {
                  success: true,
                  trace_id: 'trc_example',
                  data: {
                    recruiter_id: 'rec_120',
                    company_id: 'cmp_120',
                    status: 'active'
                  }
                }
              }
            }
          },
          400: {
            description: 'Validation error',
            content: {
              'application/json': {
                example: errorExample(
                  'validation_error',
                  'One or more request fields are invalid.',
                  { company_size: 'invalid_enum' }
                )
              }
            }
          },
          409: {
            description: 'Duplicate recruiter email',
            content: {
              'application/json': {
                example: errorExample(
                  'duplicate_recruiter_email',
                  'A recruiter with this email already exists.'
                )
              }
            }
          },
          403: {
            description: 'Forbidden',
            content: {
              'application/json': {
                example: errorExample(
                  'forbidden',
                  'Authenticated recruiter already has a recruiter profile.'
                )
              }
            }
          }
        }
      }
    },

    '/companies/get': {
      post: {
        tags: ['Companies'],
        summary: 'Fetch company metadata',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              example: {
                company_id: 'cmp_120'
              }
            }
          }
        },
        responses: {
          200: {
            description: 'Company fetched',
            content: {
              'application/json': {
                example: {
                  success: true,
                  trace_id: 'trc_example',
                  data: {
                    company: {
                      company_id: 'cmp_120',
                      company_name: 'Northstar Labs',
                      company_industry: 'Software',
                      company_size: 'large',
                      recruiter_count: 1
                    }
                  },
                  meta: {
                    cache: 'hit'
                  }
                }
              }
            }
          },
          400: {
            description: 'Validation error',
            content: {
              'application/json': {
                example: errorExample(
                  'validation_error',
                  'One or more request fields are invalid.',
                  { company_id: 'invalid_format' }
                )
              }
            }
          },
          404: {
            description: 'Not found',
            content: {
              'application/json': {
                example: errorExample(
                  'not_found',
                  'Company not found.'
                )
              }
            }
          }
        }
      }
    }
  }
};

module.exports = { swaggerUi, spec };