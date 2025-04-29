import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from "./layout/navbar/navbar.component";
import { SidebarComponent } from "./layout/sidebar/sidebar.component";
import { FooterComponent } from "./layout/footer/footer.component";

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, NavbarComponent, SidebarComponent, FooterComponent],
  template: `<!--begin::App Wrapper-->
  <div class="app-wrapper">
    <!--begin::Header-->
    <app-navbar></app-navbar>
    <!--end::Header-->
    <!--begin::Sidebar-->
    <app-sidebar class="app-sidebar"></app-sidebar>
    <!--end::Sidebar-->
    <!--begin::App Main-->
    <main class="app-main">
      <router-outlet></router-outlet>
    </main>
    <!--end::App Main-->
    <!--begin::Footer-->
    <footer class="app-footer">
      <app-footer></app-footer>
    </footer>
    <!--end::Footer-->
  </div>
  <!--end::App Wrapper-->
  `,
})
export class AppComponent {
}
