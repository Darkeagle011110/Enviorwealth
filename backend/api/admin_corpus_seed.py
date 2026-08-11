from fastapi import APIRouter

router = APIRouter()

@router.get("/corpus/recommended-sources")
async def get_recommended_sources():
    return {
        "sources": [
            {
                "name": "Verra VM0047 v1.1",
                "description": "Afforestation, Reforestation, and Revegetation Methodology",
                "url": "https://verra.org/methodologies/vm0047-afforestation-reforestation-and-revegetation/"
            },
            {
                "name": "CCTS Offset Mechanism notifications",
                "description": "Carbon Credit Trading Scheme rules by BEE",
                "url": "https://beeindia.gov.in/en/ccts"
            },
            {
                "name": "Green Credit Programme rules",
                "description": "Ministry of Environment, Forest and Climate Change (MoEFCC)",
                "url": "https://icfre.gov.in/"
            },
            {
                "name": "Gold Standard A/R",
                "description": "Afforestation/Reforestation GHG Emissions Reduction & Sequestration",
                "url": "https://globalgoals.goldstandard.org/403-ar-ghg-emissions-reduction-sequestration-methodology/"
            },
            {
                "name": "Plan Vivo Standard",
                "description": "Climate benefits from community land use projects",
                "url": "https://www.planvivo.org/plan-vivo-standard"
            },
            {
                "name": "FSI ISFR",
                "description": "India State of Forest Report (FSI)",
                "url": "https://fsi.nic.in/"
            }
        ]
    }
