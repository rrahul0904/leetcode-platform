insert into public.topics(name,slug,description,sort_order) values
('Python','python','Python coding and interview problems',10),
('SQL','sql','SQL coding, optimization, and database reasoning',20),
('PySpark','pyspark','Distributed data-processing practice',30),
('Snowflake','snowflake','Snowflake engineering and architecture',40),
('Data Engineering','data-engineering','Pipelines, reliability, modeling, governance, and operations',50),
('Cloud','cloud','AWS, Azure, and GCP architecture',60),
('AI Architecture','ai-architecture','RAG, agents, LLM systems, and AI platform design',70),
('System Design','system-design','Distributed systems and data-platform design',80)
on conflict(slug) do nothing;

insert into public.learning_paths(slug,name,description,config) values
('data-engineer','Data Engineer','SQL → Python → Spark → Airflow → scenarios','{"topics":["sql","python","pyspark","data-engineering"]}'),
('snowflake-architect','Snowflake Architect','Core → performance → security → architecture','{"topics":["snowflake"]}'),
('ai-data-architect','AI Data Architect','RAG → agents → governance → system design','{"topics":["ai-architecture","system-design"]}')
on conflict(slug) do nothing;
