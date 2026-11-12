import { InfoPage, infoMetadata } from "@/components/info-page";

export const metadata = infoMetadata(
  "소개",
  "Mallow Info Lab은 정책과 생활 정보를 짧게 정리하는 블로그입니다. 운영 주체는 마이멜로(MyMallow)입니다.",
  "/about/",
);

export default function AboutPage() {
  return (
    <InfoPage kicker="소개" title="소개" lede="정책과 생활 정보를 짧게 정리합니다.">
      <p>
        Mallow Info Lab은 매일 업데이트되는 핵심 정책과 생활 꿀팁을 모아 두는 블로그입니다. 지원
        금액처럼 자주 바뀌는 숫자보다, 신청 전에 빠지기 쉬운 기준, 서류, 시기를 먼저 짚습니다.
      </p>
      <h2>다루는 글</h2>
      <p>글의 분류는 다음 아홉 가지입니다.</p>
      <ul>
        <li>교육, 건강, 과학, IT</li>
        <li>부동산, 정부혜택, 세금</li>
        <li>정책·제도, 생활정보</li>
      </ul>
      <h2>운영</h2>
      <p>
        이 블로그의 운영 주체는{" "}
        <a href="https://mymallow.cloud/" target="_blank" rel="noopener noreferrer">
          마이멜로 (MyMallow)
        </a>
        입니다. 블로그 주소는{" "}
        <a href="https://blog.mymallow.cloud/">https://blog.mymallow.cloud/</a> 입니다.
      </p>
      <h2>글을 읽기 전에</h2>
      <p>
        글은 정보 제공을 목적으로 합니다. 지원 자격, 금액, 일정은 기관 공고에 따라 달라지므로, 신청이나
        결정 전에는 해당 기관의 최신 공고를 확인해 주세요. 건강 관련 글은 진단이나 치료를 대신하지
        않습니다.
      </p>
    </InfoPage>
  );
}
