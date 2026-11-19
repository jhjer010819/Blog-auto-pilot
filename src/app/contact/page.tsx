import { InfoPage, infoMetadata } from "@/components/info-page";

export const metadata = infoMetadata(
  "문의",
  "마이멜로 문의는 contact@mymallow.cloud 으로 받습니다.",
  "/contact/",
);

export default function ContactPage() {
  return (
    <InfoPage kicker="문의" title="문의" lede="전하고 싶은 이야기가 있다면 이메일로 보내 주세요.">
      <p>
        문의는 <a href="mailto:contact@mymallow.cloud">contact@mymallow.cloud</a> 로 받습니다. 별도의
        문의 양식은 두지 않습니다.
      </p>
    </InfoPage>
  );
}
