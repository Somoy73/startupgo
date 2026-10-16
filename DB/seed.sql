-- Startup Go seed data
-- Framework reference data: KTH Innovation Readiness Level (condensed level text)
-- and the Ocean Impact Navigator (WEF 2023 edition).
-- Startup data: funding facts come from public announcements (see source_url).
-- READINESS LEVELS AND KPI EVIDENCE LEVELS ARE SEED ESTIMATES (confidence = 'low')
-- made from public information. They must be validated with the companies.

-- ---------------------------------------------------------------------------
-- KTH IRL dimensions
-- ---------------------------------------------------------------------------
INSERT INTO readiness_dimensions (code, name, description, sort_order) VALUES
('CRL',  'Customer',       'Customer readiness: from a hunch about a need to scalable, repeatable sales.', 1),
('TRL',  'Technology',     'Technology readiness: from a research idea to a solution proven in actual operations.', 2),
('BRL',  'Business model', 'Business readiness: from a vague idea to a proven, sustainable (economic + environmental + social) business model.', 3),
('IPRL', 'IP',             'IPR readiness: from hypothesised IP to a proven IP strategy with key rights granted.', 4),
('TMRL', 'Team',           'Team readiness: from a single founder to a high-performing organisation.', 5),
('FRL',  'Funding',        'Funding readiness: from no funding insight to secured runway and full financial control.', 6);

INSERT INTO readiness_levels (dimension_code, level, summary) VALUES
('CRL',1,'A possible need is assumed; no clear customer hypotheses.'),
('CRL',2,'Secondary market research; first problem/need hypothesis.'),
('CRL',3,'Primary feedback from a few users or experts; hypothesis updated.'),
('CRL',4,'Problem confirmed by multiple customers; segments and buyer roles identified.'),
('CRL',5,'Customers confirm the product can solve their problem (problem-solution fit).'),
('CRL',6,'Customer testing confirms value; structured sales activities started.'),
('CRL',7,'Customer agreements in place; first or test sales; small active user base.'),
('CRL',8,'Market-ready product sold near target price; initial traction; sales process staffed.'),
('CRL',9,'Widespread, repeatable, scalable sales; significant traction.'),

('TRL',1,'Research results with potential applications; vague technology idea.'),
('TRL',2,'Technology concept defined; applications speculative.'),
('TRL',3,'Lab tests show the concept could work; active R&D started.'),
('TRL',4,'Components integrated and working together in the lab (initial validation).'),
('TRL',5,'Components validated in a relevant (simulated) environment.'),
('TRL',6,'Representative prototype demonstrated in a relevant environment.'),
('TRL',7,'Near-complete prototype works in an operational environment.'),
('TRL',8,'Complete technology proven in actual operations by first users.'),
('TRL',9,'Scalable technology proven in operations by several users over time.'),

('BRL',1,'Vague business idea; little market or competition insight.'),
('BRL',2,'Business concept and value proposition described; brief market familiarity.'),
('BRL',3,'Proposed business model (e.g. canvas), TAM/SAM estimates, competition defined.'),
('BRL',4,'Simplified P&L indicates viability; initial sustainability assessment (own assumptions).'),
('BRL',5,'Revenue and cost sides validated with external feedback; P&L updated.'),
('BRL',6,'Complete sustainable business model tested in realistic scenarios (pilot, pre-order).'),
('BRL',7,'First commercial revenue shows willingness to pay; key partner agreements in place.'),
('BRL',8,'1-3 years of operations show the sustainable model holds; channels and supply chain live.'),
('BRL',9,'Sustainable business model operational and proven profitable and impactful over time.'),

('IPRL',1,'Hypothesising that results might contain some form of IP.'),
('IPRL',2,'IP forms mapped; ownership clarified.'),
('IPRL',3,'Key IP described in detail; initial protectability evaluation.'),
('IPRL',4,'Protectability confirmed by professional; priorities decided.'),
('IPRL',5,'Draft IP strategy; first formal application of key IP filed.'),
('IPRL',6,'Complete IP strategy; positive response from authorities; freedom-to-operate assessed.'),
('IPRL',7,'Key IP in national/regional phase in relevant markets.'),
('IPRL',8,'IP strategy fully implemented; key IP granted in first market.'),
('IPRL',9,'IP strategy proven to create value; key IP granted in several countries.'),

('TMRL',1,'Individual lacking key competencies.'),
('TMRL',2,'1-2 people with limited competencies; first idea of needs.'),
('TMRL',3,'Some competencies present; gaps identified with a near-term plan.'),
('TMRL',4,'Committed champion; several competencies present; roles being discussed.'),
('TMRL',5,'Founding team with main competencies; shareholder agreement signed.'),
('TMRL',6,'Complementary, diverse founding team with clear CEO; advisors being recruited.'),
('TMRL',7,'Well-functioning team with clear roles; board and advisors operational.'),
('TMRL',8,'Experienced leadership team; competent board; HR processes in place.'),
('TMRL',9,'High-performing organisation with continuous development.'),

('FRL',1,'Little insight into costs or funding options.'),
('FRL',2,'Basic plan with funding options for initial milestones.'),
('FRL',3,'Funding secured for initial feasibility work (1-6 months).'),
('FRL',4,'Verification plan in place and substantially funded.'),
('FRL',5,'Investor pitch tested; 12-month budget; funding strategy decided.'),
('FRL',6,'Improved pitch tested; 3-5 year P&L and cash flow.'),
('FRL',7,'Discussions with investors around a defined offer; business plan in place.'),
('FRL',8,'Term-sheet-level discussions; due-diligence materials ready.'),
('FRL',9,'6-12+ months runway secured; full financial monitoring.');

-- ---------------------------------------------------------------------------
-- Ocean Impact Navigator
-- ---------------------------------------------------------------------------
INSERT INTO ocean_impact_areas (code, name, orientation) VALUES
('A','Sustainably managed ocean resources','Solutions to over-exploitation'),
('B','A clean ocean','Solutions for pollution'),
('C','Thriving and restored marine habitats','Solutions to physical damage of marine & coastal habitats'),
('D','Towards 1.5C','Reducing & sequestering GHG emissions'),
('E','Climate-resilient coastal communities','Reducing vulnerability & enhancing adaptive capacity'),
('F','Positive socio-economic outcomes','Well-being & equity');

INSERT INTO ocean_kpis (code, area_code, name, qualitative_only) VALUES
('A1','A','Volume of biomass preserved or restored',0),
('A2','A','Volume of seafood waste reduced',0),
('A3','A','Welfare of marine life',1),
('A4','A','Tonnes of ocean-based seaweed and bivalves produced',0),
('B1','B','Volume of primary micro-plastics diverted from nature (or landfill)',0),
('B2','B','Volume of macro-plastic diverted from nature (or landfill)',0),
('B3','B','Nitrogen/phosphorous pollution mitigated',0),
('B4','B','Volume of contaminated waste water from land-based sources diverted from waterways',0),
('B5','B','Invasive species reduced or avoided',1),
('B6','B','Reduction in other pollution (heavy metals, chemicals, sound, etc.)',0),
('C1','C','Area of coral reefs protected or restored',0),
('C2','C','Area of mangroves protected or restored',0),
('C3','C','Area of seagrasses protected or restored',0),
('C4','C','Area of salt marshes protected or restored',0),
('C5','C','Area of kelp forest protected or restored',0),
('C6','C','Area of other habitat protected or restored',0),
('D1','D','GHG emissions reduced or avoided',0),
('D2','D','GHG emissions generated',0),
('D3','D','Carbon sequestered',0),
('D4','D','NOx emissions mitigated',0),
('D5','D','SOx emissions mitigated',0),
('E1','E','Length of coastline protected',0),
('E2','E','Use of ocean information products/services in climate adaptation decisions',0),
('E3','E','Number of people supported to adapt to climate change',0),
('E4','E','Enhanced food security',1),
('F1','F','Number of jobs created',0),
('F2','F','People completing education / training programmes',0),
('F3','F','Share of employees that are women',0),
('F4','F','Entry-level wage vs local minimum wage',0),
('F5','F','Particulate emissions mitigated',0);

-- ---------------------------------------------------------------------------
-- Startups (8 real ocean-tech companies)
-- ---------------------------------------------------------------------------
INSERT INTO startups (id, slug, name, tagline, description, sector, country, city, founded_year, website, stage, pipeline_stage) VALUES
(1,'notpla','Notpla','Seaweed-based packaging that replaces single-use plastic',
 'Develops packaging and coatings made from seaweed and plants as an alternative to single-use plastic.',
 'Materials & packaging','United Kingdom','London',2014,'https://www.notpla.com','series-a','diligence'),
(2,'sofar-ocean','Sofar Ocean','Real-time ocean data from a global network of Spotter buoys',
 'Builds solar-powered Spotter buoys that report wind, wave, temperature and current data, and sells marine weather intelligence. Formed from the merger of OpenROV and Spoondrift.',
 'Ocean data','United States','San Francisco',2019,'https://www.sofarocean.com','series-b','screening'),
(3,'ocean-rainforest','Ocean Rainforest','Offshore seaweed cultivation at scale',
 'Cultivates seaweed offshore in the Faroe Islands and develops seaweed products and markets.',
 'Aquaculture','Faroe Islands','Faroe Islands',NULL,'https://www.oceanrainforest.com','series-a','diligence'),
(4,'seabound','Seabound','Onboard carbon capture for ships',
 'Builds carbon capture equipment that fits on ships to capture exhaust CO2 at the source. Y Combinator alumnus.',
 'Shipping decarbonisation','United Kingdom','London',2021,'https://www.seabound.co','seed','screening'),
(5,'oceanium','Oceanium','Seaweed biorefinery for food, materials and biodegradable products',
 'Processes farmed kelp into food ingredients, biodegradable materials and other products through its biorefinery technology.',
 'Aquaculture','United Kingdom','Oban',NULL,'https://www.oceanium.world','seed','sourced'),
(6,'seaforester','SeaForester','Restoring marine forests',
 'Marine restoration company focused on restoring kelp and other marine forests.',
 'Habitat restoration','Portugal','Lisbon',NULL,NULL,'seed','sourced'),
(7,'kelp-blue','Kelp Blue','Giant kelp forests for carbon, biodiversity and biostimulants',
 'Dutch-headquartered company cultivating giant kelp forests off Lüderitz, Namibia. Received the Zayed Sustainability Prize (Climate Action) at COP28.',
 'Aquaculture','Namibia','Lüderitz',2020,'https://kelp.blue','project-finance','sourced'),
(8,'clearbot','Clearbot','Autonomous electric boats that collect floating waste',
 'Spun out of University of Hong Kong students; builds self-driving electric boats that each collect 250-300 kg of waste per trip. Reported deployments in Hong Kong, India and Panama.',
 'Ocean cleanup','Hong Kong','Hong Kong',NULL,NULL,'seed','sourced');

INSERT INTO funding_rounds (startup_id, round_type, amount, currency, announced_on, lead_investors, notes, source_url) VALUES
(1,'series-a',20000000,'GBP','2024-09','UB Forest Industry Green Growth Fund','Series A+ (~EUR 23M).','https://maritime-forum.ec.europa.eu/eu4algae-highlight-stories-notpla-received-ps20-million-eu23-million-series-funding-revolutionise_en'),
(2,'series-b',39000000,'USD','2021-11','Union Square Ventures; Foundry Group','Aggregators list total raised between ~$47M and ~$73M; unverified.','https://techcrunch.com/2021/11/03/sofar-nets-a-39m-round-b-to-grow-its-ocean-monitoring-autonomous-buoy-network'),
(3,'series-a',6200000,'USD','2023-02','The Grantham Foundation','With Katapult Ocean (Deep Blue fund), Builders Vision, Ocean Born Foundation, WWF-US.','https://www.undercurrentnews.com/2023/02/15/seaweed-farmer-ocean-rainforest-snags-6-2m-in-series-a-funding/'),
(4,'seed',4400000,'USD','2022-05','Lowercarbon Capital','With Eastern Pacific Shipping, Emles, Hawktail, Rebel Fund, Soma Capital, Y Combinator.','https://techcrunch.com/2022/05/20/carbon-capture-container-ships'),
(4,'grant',1100000,'GBP','2025','UK Clean Maritime Demonstration Competition (Round 6)','Reported by aggregators; verify against the UK DfT announcement.',NULL),
(5,'seed',2000000,'GBP',NULL,'Green Angel Syndicate','Seed II first close; WWF anchor; Katapult Ocean, Sky Ocean Ventures, Scottish Enterprise previously invested.','https://www.seafoodsource.com/news/business-finance/kelp-focused-firm-oceanium-garners-gbp-2-million-investment'),
(5,'seed',2600000,'USD','2023-09','Builders Vision','Pre-Series A raise to commercialise; WWF and Green Angel Ventures participated.','https://www.foodnavigator.com/Article/2023/09/15/Seaweed-start-up-secures-fresh-funds-million-to-scale-and-commercialise'),
(6,'seed',1900000,'USD','2025-10','WWF; Schmidt Marine Technology Partners','Co-led.','https://seedtable.com/companies/seaforester/funding-rounds/seed-2025-10'),
(7,'project-finance',60000000,'USD','2023-12','Climate Fund Managers; Eos Capital','In-principle commitment, released in phases, pending investment and Namibian regulatory approvals. A separate ~$80M blue bond was planned on the NSX.','https://thefishsite.com/es/articles/kelp-blue-seeks-80-million-blue-bond'),
(8,'seed',NULL,NULL,'2022-09','Alibaba Hong Kong Entrepreneurs Fund','Amount undisclosed. Co-investors: Earth Venture Capital, Asia Sustainability Angels, CarbonX Capital.','https://hivelife.com/clearbot/');

INSERT INTO readiness_assessments (startup_id, assessed_on, assessor, confidence, crl, trl, brl, iprl, tmrl, frl, rationale) VALUES
(1,'2026-10-16','Startup Go seed estimate','low',8,8,7,6,7,8,'Products on the market and a large Series A+ imply commercial traction; IP position not verified.'),
(2,'2026-10-16','Startup Go seed estimate','low',8,9,7,6,8,8,'Thousands of buoys deployed across all major oceans; Series B-backed team.'),
(3,'2026-10-16','Startup Go seed estimate','low',6,7,6,4,7,7,'Operating offshore farms in the Faroes; Series A to scale production and markets.'),
(4,'2026-10-16','Startup Go seed estimate','low',6,6,5,5,6,6,'Seed-stage hardware moving through ship pilots, with government grant support.'),
(5,'2026-10-16','Startup Go seed estimate','low',5,6,5,5,6,5,'Biorefinery tech scaling ahead of a planned Series A for a commercial plant.'),
(6,'2026-10-16','Startup Go seed estimate','low',4,5,4,3,5,5,'Fresh seed round; restoration business model still being validated.'),
(7,'2026-10-16','Startup Go seed estimate','low',5,6,5,3,7,6,'Large-scale pilot forest in Namibia; project finance committed in principle but not yet confirmed as drawn.'),
(8,'2026-10-16','Startup Go seed estimate','low',6,7,5,4,5,5,'Robots deployed in several countries; seed-stage company, round size undisclosed.');

INSERT INTO startup_ocean_kpis (startup_id, kpi_code, evidence_level, claim, source_url) VALUES
(1,'B2',2,'Seaweed-based packaging replaces single-use plastic items.','https://maritime-forum.ec.europa.eu/eu4algae-highlight-stories-notpla-received-ps20-million-eu23-million-series-funding-revolutionise_en'),
(1,'D1',1,'Lower-carbon materials than fossil plastics (claimed).',NULL),
(2,'E2',2,'Real-time wind, wave, temperature and current data used in marine decisions.','https://techcrunch.com/2021/11/03/sofar-nets-a-39m-round-b-to-grow-its-ocean-monitoring-autonomous-buoy-network'),
(2,'D1',1,'Weather routing can reduce ship fuel use (claimed).',NULL),
(3,'A4',2,'Produces offshore-farmed seaweed in the Faroe Islands.','https://www.undercurrentnews.com/2023/02/15/seaweed-farmer-ocean-rainforest-snags-6-2m-in-series-a-funding/'),
(3,'D3',1,'Seaweed cultivation as a carbon sink (claimed).',NULL),
(3,'E4',1,'Seaweed as a food and feed resource.',NULL),
(4,'D1',2,'Captures CO2 from ship exhaust onboard.','https://techcrunch.com/2022/05/20/carbon-capture-container-ships'),
(4,'D5',1,'Co-capture of sulphur emissions (claimed).',NULL),
(5,'A4',1,'Creates demand for farmed kelp.',NULL),
(5,'B2',1,'Biodegradable materials as plastic alternatives.','https://www.seafoodsource.com/news/business-finance/kelp-focused-firm-oceanium-garners-gbp-2-million-investment'),
(6,'C5',2,'Restores kelp / marine forests.','https://seedtable.com/companies/seaforester/funding-rounds/seed-2025-10'),
(6,'A1',1,'Restored forests increase marine biomass (claimed).',NULL),
(6,'D3',1,'Blue-carbon sequestration (claimed).',NULL),
(7,'C5',2,'Cultivates giant kelp forests off Lüderitz, Namibia.','https://thefishsite.com/es/articles/kelp-blue-seeks-80-million-blue-bond'),
(7,'D3',1,'Carbon capture from kelp forests (claimed).',NULL),
(7,'A1',1,'Kelp forest habitat increases local biomass (claimed).',NULL),
(7,'F1',1,'Creates local jobs in Lüderitz (claimed).',NULL),
(8,'B2',2,'Each robot collects 250-300 kg of floating waste per trip.','https://hivelife.com/clearbot/'),
(8,'F1',1,'Deployments create local operator jobs (claimed).',NULL);

INSERT INTO sources (startup_id, title, url) VALUES
(1,'EU Maritime Forum: Notpla £20M Series A+','https://maritime-forum.ec.europa.eu/eu4algae-highlight-stories-notpla-received-ps20-million-eu23-million-series-funding-revolutionise_en'),
(2,'TechCrunch: Sofar nets $39M Series B','https://techcrunch.com/2021/11/03/sofar-nets-a-39m-round-b-to-grow-its-ocean-monitoring-autonomous-buoy-network'),
(3,'Undercurrent News: Ocean Rainforest $6.2M Series A','https://www.undercurrentnews.com/2023/02/15/seaweed-farmer-ocean-rainforest-snags-6-2m-in-series-a-funding/'),
(4,'TechCrunch: Seabound carbon capture for container ships','https://techcrunch.com/2022/05/20/carbon-capture-container-ships'),
(4,'TNW: UK startup Seabound','https://thenextweb.com/news/uk-startup-seabound-carbon-capture-shipping'),
(5,'FoodNavigator: Oceanium secures fresh funds','https://www.foodnavigator.com/Article/2023/09/15/Seaweed-start-up-secures-fresh-funds-million-to-scale-and-commercialise'),
(5,'SeafoodSource: Oceanium £2M','https://www.seafoodsource.com/news/business-finance/kelp-focused-firm-oceanium-garners-gbp-2-million-investment'),
(6,'Seedtable: SeaForester seed 2025-10','https://seedtable.com/companies/seaforester/funding-rounds/seed-2025-10'),
(7,'The Fish Site: Kelp Blue seeks $80M blue bond','https://thefishsite.com/es/articles/kelp-blue-seeks-80-million-blue-bond'),
(7,'The Brief: Kelp Blue blue bonds','https://thebrief.com.na/2023/12/kelp-blue-plans-n1-4bn-raise-through-namibias-first-ever-blue-bonds-offering/'),
(8,'HiveLife: Clearbot','https://hivelife.com/clearbot/');
