const router = require('express').Router();
const { getDB } = require('../db/mysql');
const { getRedis } = require('../db/redis');
const { requireAuth } = require('../middleware/auth');
const { AppError } = require('../middleware/errorHandler');

function isValidCompanyId(value) {
  return typeof value === 'string' && /^cmp_[A-Za-z0-9_]+$/.test(value);
}

function fromDbCompanySize(dbSize) {
  const map = {
    '1-10': 'startup',
    '11-50': 'small',
    '51-200': 'medium',
    '201-500': 'large',
    '501-1000': 'large',
    '1001-5000': 'enterprise',
    '5000+': 'enterprise'
  };
  return map[dbSize] || 'medium';
}

function buildCompanyResponse(row) {
  return {
    company_id: row.company_id,
    company_name: row.company_name,
    company_industry: row.company_industry,
    company_size: fromDbCompanySize(row.company_size),
    recruiter_count: Number(row.recruiter_count || 0)
  };
}

router.post('/get', requireAuth, async (req, res, next) => {
  try {
    const { company_id } = req.body || {};

    if (!company_id) {
      return next(
        new AppError(
          400,
          'validation_error',
          'One or more request fields are invalid.',
          false,
          { company_id: 'required' }
        )
      );
    }

    if (!isValidCompanyId(company_id)) {
      return next(
        new AppError(
          400,
          'validation_error',
          'One or more request fields are invalid.',
          false,
          { company_id: 'invalid_format' }
        )
      );
    }

    let redis = null;
    try {
      redis = getRedis();
    } catch (e) {
      console.warn('[companies/get] Redis unavailable');
    }

    const cacheKey = `company:${company_id}`;

    if (redis) {
      try {
        const cached = await redis.get(cacheKey);
        if (cached) {
          return res.json({
            success: true,
            trace_id: req.traceId,
            data: {
              company: JSON.parse(cached)
            },
            meta: {
              cache: 'hit'
            }
          });
        }
      } catch (err) {
        console.warn('[companies/get] Redis read failed:', err.message);
      }
    }

    const db = getDB();
    const [rows] = await db.execute(
      `
        SELECT
          c.company_id,
          c.company_name,
          c.company_industry,
          c.company_size,
          COUNT(r.recruiter_id) AS recruiter_count
        FROM companies c
        LEFT JOIN recruiters r
          ON r.company_id = c.company_id
          AND r.is_deleted = 0
        WHERE c.company_id = ?
        GROUP BY c.company_id, c.company_name, c.company_industry, c.company_size
        LIMIT 1
      `,
      [company_id]
    );

    const company = rows[0];

    if (!company) {
      return next(new AppError(404, 'not_found', 'Company not found.', false, {}));
    }

    const responseCompany = buildCompanyResponse(company);

    if (redis) {
      try {
        await redis.set(cacheKey, JSON.stringify(responseCompany), 'EX', 3600);
      } catch (err) {
        console.warn('[companies/get] Redis write failed:', err.message);
      }
    }

    return res.json({
      success: true,
      trace_id: req.traceId,
      data: {
        company: responseCompany
      },
      meta: {
        cache: 'miss'
      }
    });
  } catch (err) {
    return next(err);
  }
});

module.exports = router;