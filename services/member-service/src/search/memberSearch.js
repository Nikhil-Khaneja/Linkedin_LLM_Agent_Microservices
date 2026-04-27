/**
 * Elasticsearch Member/People Search
 */
const { getES, isReady } = require('../db/elasticsearch');
const { getDB } = require('../db/mysql');

const MEMBERS_MAPPING = {
  mappings: {
    properties: {
      member_id:     { type: 'keyword' },
      first_name:    { type: 'text', fields: { keyword: { type: 'keyword' } } },
      last_name:     { type: 'text', fields: { keyword: { type: 'keyword' } } },
      full_name:     { type: 'text', analyzer: 'english' },
      headline:      { type: 'text', analyzer: 'english' },
      about_summary: { type: 'text', analyzer: 'english' },
      city:          { type: 'text', fields: { keyword: { type: 'keyword' } } },
      state:         { type: 'keyword' },
      skills:        { type: 'text', analyzer: 'english' },
    }
  }
};

async function ensureMembersIndex() {
  const es = getES();
  if (!es || !isReady()) return;
  try {
    const exists = await es.indices.exists({ index: 'members' });
    if (!exists) {
      await es.indices.create({ index: 'members', body: MEMBERS_MAPPING });
      console.log('[es-members] members index created');
    }
  } catch (e) {
    console.error('[es-members] Failed to create index:', e.message);
  }
}

async function syncMembersToES() {
  const es = getES();
  if (!es || !isReady()) return;
  const db = getDB();
  try {
    const [members] = await db.execute(`
      SELECT m.member_id, m.first_name, m.last_name, m.headline, m.about_summary, m.city, m.state,
             GROUP_CONCAT(ms.skill_name SEPARATOR ' ') as skills
      FROM members m
      LEFT JOIN member_skills ms ON m.member_id = ms.member_id
      WHERE m.is_deleted = 0
      GROUP BY m.member_id
      LIMIT 10000
    `);
    if (members.length === 0) return;
    const body = members.flatMap(m => [
      { index: { _index: 'members', _id: m.member_id } },
      { ...m, full_name: `${m.first_name} ${m.last_name}`, skills: m.skills || '' }
    ]);
    await es.bulk({ refresh: true, body });
    console.log(`[es-members] ✅ Synced ${members.length} members to Elasticsearch`);
  } catch (e) {
    console.error('[es-members] Sync failed:', e.message);
  }
}

async function searchMembers({ keyword, location, skill, page = 1, page_size = 20 }) {
  const es = getES();

  if (es && isReady() && keyword) {
    try {
      const must = [{
        multi_match: {
          query: keyword,
          fields: ['full_name^4', 'first_name^3', 'last_name^3', 'headline^2', 'skills^2', 'about_summary'],
          fuzziness: 'AUTO',
          prefix_length: 1,
          operator: 'or',
        }
      }];
      const filter = [];
      if (location) filter.push({ bool: { should: [{ match: { city: location } }, { term: { state: location } }] } });
      if (skill)    must.push({ match: { skills: { query: skill, fuzziness: 'AUTO' } } });

      const result = await es.search({
        index: 'members',
        body: {
          query: { bool: { must, filter } },
          sort: [{ _score: 'desc' }],
          from: (page - 1) * page_size,
          size: page_size,
        }
      });
      const members = result.hits.hits.map(h => h._source);
      console.log(`[es-members] "${keyword}" → ${members.length} results`);
      return { members, source: 'elasticsearch' };
    } catch (e) {
      console.warn('[es-members] Fallback to MySQL:', e.message);
    }
  }

  // MySQL fallback
  const db = getDB();
  let query = `SELECT m.member_id, m.first_name, m.last_name, m.headline, m.city, m.state
               FROM members m WHERE m.is_deleted = 0`;
  const params = [];
  if (keyword) {
    query += ` AND (m.first_name LIKE ? OR m.last_name LIKE ? OR CONCAT(m.first_name,' ',m.last_name) LIKE ? OR MATCH(m.headline, m.about_summary) AGAINST(? IN BOOLEAN MODE))`;
    params.push('%'+keyword+'%','%'+keyword+'%','%'+keyword+'%',keyword+'*');
  }
  if (location) { query += ' AND (m.city LIKE ? OR m.state LIKE ?)'; params.push('%'+location+'%','%'+location+'%'); }
  query += ` LIMIT ${page_size} OFFSET ${(page-1)*page_size}`;
  const [rows] = await db.execute(query, params);
  return { members: rows, source: 'mysql' };
}

async function indexMember(memberData) {
  const es = getES();
  if (!es || !isReady()) return;
  try {
    await es.index({
      index: 'members',
      id: memberData.member_id,
      document: { ...memberData, full_name: `${memberData.first_name} ${memberData.last_name}` },
    });
  } catch {}
}

module.exports = { ensureMembersIndex, syncMembersToES, searchMembers, indexMember };
