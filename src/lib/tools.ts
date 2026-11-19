export type Tool = {
  name: string;
  description: string;
  href?: string;
  live: boolean;
  image?: string;
  imageAlt: string;
};

export const TOOLS: Tool[] = [
  {
    name: "닌텐도 게임 추천",
    description: "아이 연령과 성향에 맞는 스위치 게임을 골라 줍니다.",
    href: "https://kidgame.mymallow.cloud/",
    live: true,
    image: "/images/tools/kidgame.png",
    imageAlt: "닌텐도 게임 추천 첫 화면",
  },
  {
    name: "교외체험학습 문장 메이커",
    description: "체험학습 신청서와 결과보고서 문장을 만들어 줍니다.",
    href: "https://fieldtrip.mymallow.cloud/",
    live: true,
    image: "/images/tools/fieldtrip.jpg",
    imageAlt: "교외체험학습 제출 문장 메이커 화면",
  },
  {
    name: "타로",
    description: "심심할 때 고르는 가벼운 결과 카드입니다.",
    href: "https://taro.mymallow.cloud/",
    live: true,
    image: "/images/tools/taro.png",
    imageAlt: "타로 테스트 표지",
  },
  {
    name: "초등 시간표",
    description: "아이 하루 시간표를 짜는 도구입니다.",
    live: false,
    imageAlt: "초등 시간표",
  },
];

export const FEATURED_TOOL = TOOLS[0];
